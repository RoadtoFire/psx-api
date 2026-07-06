"""
Management command: backfill_macro

Seeds MacroSnapshot and MacroWarning with monthly historical data from 2021–2026
so the frontend charts work from day one.

Data: hardcoded quarterly anchor points (SBP Statistical Bulletins, PBS CPI releases,
IMF country reports) interpolated monthly. Brent crude from yfinance.

Run once after deployment: python manage.py backfill_macro
Safe to re-run — uses update_or_create so existing rows are not duplicated.
"""

from datetime import date, datetime
from django.core.management.base import BaseCommand

from stocks.models import MacroSnapshot, MacroWarning
from stocks.management.commands.update_macro import (
    reserves_signal, oil_signal, real_rate_signal, composite_signal
)

# Quarterly anchor points — (YYYY-MM-DD, kibor_6m%, cpi_yoy%, pkr_usd, sbp_reserves_usd_bn)
# Sources: SBP Statistical Bulletins, PBS CPI releases, IMF country reports.
_MACRO_HISTORY = [
    ("2021-01-01",  7.5,  5.7, 160.0, 13.1),
    ("2021-04-01",  7.5,  8.6, 153.5, 16.0),
    ("2021-07-01",  8.0,  9.0, 162.0, 17.5),
    ("2021-10-01",  9.5, 11.5, 169.0, 17.1),
    ("2022-01-01", 11.5, 12.2, 176.5, 16.4),
    ("2022-04-01", 12.5, 21.3, 186.0, 10.7),
    ("2022-07-01", 15.0, 24.9, 239.5,  7.9),
    ("2022-10-01", 16.5, 26.6, 221.5,  7.6),
    ("2023-01-01", 17.0, 27.6, 225.0,  3.7),
    ("2023-04-01", 21.0, 36.4, 285.0,  4.5),
    ("2023-07-01", 22.0, 29.4, 285.0,  8.5),
    ("2023-10-01", 22.0, 26.9, 283.0,  7.6),
    ("2024-01-01", 22.0, 28.3, 280.5,  8.0),
    ("2024-04-01", 22.0, 17.3, 278.0,  9.1),
    ("2024-07-01", 19.5,  9.6, 278.5,  9.4),
    ("2024-10-01", 15.0,  7.2, 278.0, 11.0),
    ("2025-01-01", 13.0,  4.1, 279.0, 11.8),
    ("2025-04-01", 12.5,  3.0, 280.0, 13.0),
    ("2025-07-01", 12.0,  3.5, 280.5, 14.5),
    ("2025-10-01", 11.5,  5.0, 280.0, 15.0),
    ("2026-01-01", 12.0,  8.0, 279.0, 15.5),
    ("2026-04-01", 12.25, 10.9, 278.6, 15.9),
]

_MONTHLY_IMPORTS_USD_BN = 5.57   # World Bank BM.GSR.GNFS.CD ÷ 12


def _interpolate(target: date) -> tuple[float, float, float, float]:
    pts = [(datetime.strptime(d, "%Y-%m-%d").date(), *vals) for d, *vals in _MACRO_HISTORY]
    pts.sort(key=lambda x: x[0])

    if target <= pts[0][0]:
        return pts[0][1:]
    if target >= pts[-1][0]:
        return pts[-1][1:]

    for i in range(len(pts) - 1):
        d0, k0, c0, p0, r0 = pts[i]
        d1, k1, c1, p1, r1 = pts[i + 1]
        if d0 <= target <= d1:
            span = (d1 - d0).days
            frac = (target - d0).days / span if span else 0
            lerp = lambda a, b: a + (b - a) * frac
            return lerp(k0, k1), lerp(c0, c1), lerp(p0, p1), lerp(r0, r1)

    return pts[-1][1:]


def _brent_monthly(years: int) -> dict[str, float]:
    try:
        import yfinance as yf
        today = date.today()
        start = date(today.year - years, today.month, 1)
        df = yf.Ticker("BZ=F").history(start=str(start), end=str(today))
        if df.empty:
            return {}
        df.index = df.index.tz_localize(None)
        df["ym"] = df.index.to_period("M")
        monthly = df.groupby("ym")["Close"].mean()
        return {str(ym): round(float(v), 2) for ym, v in monthly.items()}
    except Exception:
        return {}


class Command(BaseCommand):
    help = 'Seed MacroSnapshot + MacroWarning with monthly historical data (2021–present)'

    def add_arguments(self, parser):
        parser.add_argument('--years', type=int, default=5)

    def handle(self, *args, **options):
        years = options['years']
        self.stdout.write(f"Fetching {years} years of Brent crude history…")
        brent_monthly = _brent_monthly(years)
        self.stdout.write(f"Got {len(brent_monthly)} months of Brent data")

        today = date.today()
        cur = date(today.year - years, today.month, 1)
        snap_count = warn_count = 0

        while cur <= today:
            ym = cur.strftime("%Y-%m")
            kibor, cpi, pkr_usd, sbp_res = _interpolate(cur)
            brent = brent_monthly.get(ym)
            import_cover = round(sbp_res / _MONTHLY_IMPORTS_USD_BN, 2)

            MacroSnapshot.objects.update_or_create(
                date=cur,
                defaults={
                    "kibor_6m": round(kibor, 2),
                    "kibor_1y": round(kibor * 1.05, 2),
                    "pkr_usd_rate": round(pkr_usd, 2),
                    "source": "backfill",
                }
            )
            snap_count += 1

            real_rate = round(kibor - cpi, 2)
            res_sig  = reserves_signal(import_cover)
            oil_sig  = oil_signal(brent) if brent else "UNKNOWN"
            rr_sig   = real_rate_signal(real_rate)
            score, composite = composite_signal(res_sig, oil_sig, rr_sig)

            MacroWarning.objects.update_or_create(
                date=cur,
                defaults={
                    "sbp_fx_reserves_usd_bn": round(sbp_res, 3),
                    "monthly_imports_usd_bn": _MONTHLY_IMPORTS_USD_BN,
                    "import_cover_months": import_cover,
                    "reserves_signal": res_sig,
                    "brent_crude_usd": brent,
                    "oil_signal": oil_sig,
                    "cpi_yoy": round(cpi, 2),
                    "real_rate": real_rate,
                    "real_rate_signal": rr_sig,
                    "macro_stress_score": score,
                    "composite_signal": composite,
                }
            )
            warn_count += 1

            # Advance one month
            cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)

        self.stdout.write(self.style.SUCCESS(
            f"Backfill complete: {snap_count} snapshot rows, {warn_count} warning rows"
        ))
