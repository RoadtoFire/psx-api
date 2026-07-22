"""
Management command: update_macro

Scrapes daily macro data for Pakistan and saves to MacroSnapshot + MacroWarning.
Ported from psx_buffet/scrapers/macro_scraper.py — same data sources, same signal thresholds.

Data sources:
  SBP ecodata page  → KIBOR 6M/1Y, PKR/USD, SBP FX reserves
  PBS SDMX endpoint → Pakistan CPI YoY
  Yahoo Finance      → Brent crude (BZ=F)
  World Bank API     → Pakistan monthly imports (BM.GSR.GNFS.CD)
"""

import io
import logging
import re
import time
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand

from stocks.models import CronLog, MacroConfig, MacroSnapshot, MacroWarning

logger = logging.getLogger(__name__)

# ── Thresholds (matching CLAUDE.md §6.5–6.8) ──────────────────────────────────
RESERVES_GREEN  = 3.0     # months import cover
RESERVES_YELLOW = 2.0
OIL_YELLOW      = 90.0    # USD/bbl
OIL_RED         = 110.0
REAL_RATE_GREEN  = 2.0    # KIBOR − CPI %
REAL_RATE_RED    = -5.0
ERP_GREEN        = 5.0    # earnings yield − KIBOR %
ERP_RED          = 0.0
DIVIDEND_GAP_RED = -5.0

_SBP_URL = "https://www.sbp.org.pk/ecodata/kibor_index.asp"
_PBS_URL  = "https://www.pbs.gov.pk/cpi"
_WB_URL   = "https://api.worldbank.org/v2/country/PK/indicator/BM.GSR.GNFS.CD"


def _session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    })
    return s


def _f(v) -> Optional[float]:
    try:
        return float(str(v).strip().replace(",", "")) if v is not None else None
    except (ValueError, InvalidOperation):
        return None


# ── SBP page: KIBOR + PKR/USD + FX reserves ───────────────────────────────────

def fetch_sbp(sess) -> dict:
    """
    One HTTP request → KIBOR 6M/1Y, PKR/USD, SBP FX reserves.
    Returns empty dict on any failure — callers tolerate None for all fields.
    """
    try:
        resp = sess.get(_SBP_URL, timeout=25)
        resp.raise_for_status()
        text = re.sub(r"\s+", " ", BeautifulSoup(resp.text, "html.parser").get_text(" "))

        out = {}

        m = re.search(r"\b6-M\s+([\d.]+)\s+([\d.]+)", text)
        if m:
            out["kibor_6m"] = _f(m.group(2))

        m = re.search(r"\b12-M\s+([\d.]+)\s+([\d.]+)", text)
        if m:
            out["kibor_1y"] = _f(m.group(2))

        m = re.search(r"M2M Revaluation Rate\s+([\d.]+)", text)
        if m:
            out["pkr_usd_rate"] = _f(m.group(1))

        m = re.search(r"SBP.{1,3}Reserves\s+([\d,]+\.?\d*)", text)
        if m:
            val = _f(m.group(1).replace(",", ""))
            if val is not None and 1_000 <= val <= 60_000:
                out["sbp_fx_reserves_mn"] = val
            elif val is not None:
                logger.warning("SBP reserves value %s mn USD outside plausible range — page may have changed", val)

        logger.info("SBP → KIBOR 6m=%s 1y=%s | PKR/USD=%s | Reserves=%s mn",
                    out.get("kibor_6m"), out.get("kibor_1y"),
                    out.get("pkr_usd_rate"), out.get("sbp_fx_reserves_mn"))
        return out

    except Exception:
        logger.error("SBP page fetch failed", exc_info=True)
        return {}


# ── PBS CPI (monthly SDMX) ────────────────────────────────────────────────────

def fetch_cpi(sess) -> Optional[float]:
    """Fetch Pakistan CPI YoY % from PBS SDMX endpoint."""
    try:
        resp = sess.get(_PBS_URL, timeout=25)
        resp.raise_for_status()

        pcpi_block = re.search(
            r'INDICATOR="PCPI_IX"[^>]*>(.*?)(?=<(?:\w+:)?Series\s|</(?:\w+:)?DataSet)',
            resp.text,
            re.DOTALL,
        )
        if not pcpi_block:
            logger.warning("CPI: PCPI_IX series not found in PBS SDMX response")
            return None

        obs_raw = re.findall(
            r'TIME_PERIOD="(\d{4}-\d{2})" OBS_VALUE="([\d.]+)"',
            pcpi_block.group(1),
        )
        if len(obs_raw) < 13:
            logger.warning("CPI: fewer than 13 monthly observations — cannot compute YoY")
            return None

        obs = sorted((tp, float(v)) for tp, v in obs_raw)
        curr_tp, curr_val = obs[-1]
        prev_tp, prev_val = obs[-13]
        yoy = round((curr_val / prev_val - 1) * 100, 2)
        logger.info("CPI YoY: %.2f%% (%s vs %s)", yoy, curr_tp, prev_tp)
        return yoy

    except Exception:
        logger.error("CPI scrape failed", exc_info=True)
        return None


# ── Brent crude (yfinance) ────────────────────────────────────────────────────

def fetch_brent() -> Optional[float]:
    """Fetch crude oil price. Tries Brent (BZ=F) first, falls back to WTI (CL=F)."""
    try:
        import yfinance as yf
        for ticker in ("BZ=F", "CL=F"):
            hist = yf.Ticker(ticker).history(period="5d")
            if not hist.empty:
                price = round(float(hist["Close"].iloc[-1]), 2)
                logger.info("Crude oil (%s): $%.2f", ticker, price)
                return price
        logger.warning("Brent/WTI: all yfinance tickers returned empty history")
        return None
    except Exception:
        logger.error("Brent scrape failed", exc_info=True)
        return None


# ── World Bank: monthly imports ───────────────────────────────────────────────

def fetch_monthly_imports(sess) -> Optional[float]:
    """Pakistan monthly goods+services imports in USD bn (World Bank, ~1yr lag)."""
    try:
        resp = sess.get(_WB_URL, params={"format": "json", "mrv": 2}, timeout=20)
        resp.raise_for_status()
        payload = resp.json()

        if not payload or len(payload) < 2 or not payload[1]:
            logger.warning("World Bank: unexpected response for PK imports")
            return None

        for rec in payload[1]:
            value = rec.get("value")
            if value is not None:
                monthly_bn = round(float(value) / 1e9 / 12, 2)
                logger.info("World Bank imports %s: $%.2f bn/month", rec.get("date"), monthly_bn)
                return monthly_bn

        logger.warning("World Bank: both returned years are null for PK imports")
        return None

    except Exception:
        logger.error("World Bank imports fetch failed", exc_info=True)
        return None


# ── Signal logic ──────────────────────────────────────────────────────────────

def reserves_signal(import_cover: Optional[float]) -> str:
    if import_cover is None:
        return "UNKNOWN"
    if import_cover >= RESERVES_GREEN:
        return "GREEN"
    if import_cover >= RESERVES_YELLOW:
        return "YELLOW"
    return "RED"


def oil_signal(price: float) -> str:
    if price > OIL_RED:
        return "RED"
    if price > OIL_YELLOW:
        return "YELLOW"
    return "GREEN"


def real_rate_signal(rr: float) -> str:
    if rr > REAL_RATE_GREEN:
        return "GREEN"
    if rr < REAL_RATE_RED:
        return "RED"
    return "YELLOW"


def erp_signal(market_erp: Optional[float], dividend_gap: Optional[float]) -> Optional[str]:
    gap = dividend_gap

    if market_erp is not None:
        if market_erp > ERP_GREEN and (gap is None or gap > 0):
            return "GREEN"
        if market_erp < ERP_RED or (gap is not None and gap < DIVIDEND_GAP_RED):
            return "RED"
        return "YELLOW"

    if gap is not None:
        return "RED" if gap < DIVIDEND_GAP_RED else "YELLOW"

    return None


def composite_signal(res_sig: str, oil_sig: str, rr_sig: str) -> tuple[int, str]:
    red_count = sum([res_sig == "RED", oil_sig == "RED", rr_sig == "RED"])
    label = {0: "CALM", 1: "WATCH", 2: "STRESSED", 3: "PEAK_STRESS"}[red_count]
    return red_count, label


# ── Main run ──────────────────────────────────────────────────────────────────

def run_update() -> tuple[MacroSnapshot, MacroWarning]:
    sess = _session()

    # One request covers KIBOR, PKR/USD, and FX reserves
    sbp = fetch_sbp(sess)
    kibor_6m   = sbp.get("kibor_6m")
    kibor_1y   = sbp.get("kibor_1y")
    pkr_usd    = sbp.get("pkr_usd_rate")
    reserves_mn = sbp.get("sbp_fx_reserves_mn")

    cpi   = fetch_cpi(sess)
    brent = fetch_brent()
    monthly_imports = fetch_monthly_imports(sess)

    # ERP calculation — uses forward PE from MacroConfig if set
    config = MacroConfig.get()
    forward_pe = config.kse100_forward_pe
    earnings_yield = round(100.0 / forward_pe, 4) if forward_pe else None
    market_erp_val = None
    if earnings_yield is not None and kibor_6m is not None:
        market_erp_val = round(earnings_yield - kibor_6m, 4)

    erp_sig = erp_signal(market_erp_val, None)

    snapshot, _ = MacroSnapshot.objects.update_or_create(
        date=date.today(),
        defaults={
            "kibor_6m": kibor_6m,
            "kibor_1y": kibor_1y,
            "pkr_usd_rate": pkr_usd,
            "kse100_forward_pe": forward_pe,
            "kse100_earnings_yield": earnings_yield,
            "market_erp": market_erp_val,
            "erp_signal": erp_sig,
            "source": "sbp_website",
        }
    )

    # Warning signals
    reserves_bn = round(reserves_mn / 1000, 3) if reserves_mn else None
    import_cover = None
    if reserves_bn and monthly_imports:
        import_cover = round(reserves_bn / monthly_imports, 2)

    real_rate = None
    rr_sig = "UNKNOWN"
    if kibor_6m is not None and cpi is not None:
        real_rate = round(kibor_6m - cpi, 2)
        rr_sig = real_rate_signal(real_rate)

    oil_sig = oil_signal(brent) if brent is not None else "UNKNOWN"
    res_sig = reserves_signal(import_cover)
    score, composite = composite_signal(res_sig, oil_sig, rr_sig)

    warning, _ = MacroWarning.objects.update_or_create(
        date=date.today(),
        defaults={
            "sbp_fx_reserves_usd_bn": reserves_bn,
            "monthly_imports_usd_bn": monthly_imports,
            "import_cover_months": import_cover,
            "reserves_signal": res_sig,
            "brent_crude_usd": brent,
            "oil_signal": oil_sig,
            "cpi_yoy": cpi,
            "real_rate": real_rate,
            "real_rate_signal": rr_sig,
            "macro_stress_score": score,
            "composite_signal": composite,
        }
    )

    logger.info(
        "Macro update complete | KIBOR=%.2f%% CPI=%.2f%% Brent=$%.0f "
        "cover=%.1fmo composite=%s ERP=%s",
        kibor_6m or 0, cpi or 0, brent or 0,
        import_cover or 0, composite, erp_sig,
    )
    return snapshot, warning


class Command(BaseCommand):
    help = 'Scrape daily macro data: KIBOR, CPI, Brent crude, FX reserves → MacroSnapshot + MacroWarning'

    def handle(self, *args, **options):
        out = io.StringIO()
        start = time.time()
        success = True

        try:
            snapshot, warning = run_update()
            msg = (
                f"MacroSnapshot: KIBOR={snapshot.kibor_6m}% | ERP={snapshot.erp_signal}\n"
                f"MacroWarning: {warning.composite_signal} | Brent=${warning.brent_crude_usd} "
                f"| CPI={warning.cpi_yoy}% | Cover={warning.import_cover_months}mo"
            )
            out.write(msg)
            self.stdout.write(self.style.SUCCESS(msg))
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            out.write(tb)
            self.stderr.write(tb)
            success = False

        duration = round(time.time() - start, 2)
        CronLog.objects.create(
            name='update_macro',
            success=success,
            output=out.getvalue()[:5000],
            duration_seconds=duration,
        )
