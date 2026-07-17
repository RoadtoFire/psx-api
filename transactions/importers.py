"""
Transaction bulk import: CSV/Excel normalizer + Gemini Flash fallback + image OCR.

Pipeline:
  1. Detect file type (csv / xlsx / image)
  2. For csv/xlsx: run header normalizer first (free, no API)
  3. If normalizer maps < 3 columns: call Gemini Flash (free tier)
  4. For images: always call Gemini Flash (multimodal OCR)
  5. Return list of raw dicts; caller validates against TransactionSerializer
"""

import base64
import csv
import io
import json
import logging
import re
from typing import Optional

import requests
from dateutil import parser as dateutil_parser

logger = logging.getLogger(__name__)

# ── Column synonym maps ───────────────────────────────────────────────────────

_SYNONYMS = {
    "stock_symbol": {
        "symbol", "scrip", "ticker", "script", "stock", "security", "code",
        "stock symbol", "company", "company code", "instrument",
    },
    "date": {
        "date", "trade date", "transaction date", "settlement date",
        "value date", "t-date", "tdate", "booking date",
    },
    "transaction_type": {
        "type", "transaction type", "buy/sell", "side", "order type",
        "action", "trade type", "bs", "b/s",
    },
    "shares": {
        "shares", "quantity", "qty", "volume", "units", "no. of shares",
        "no of shares", "number of shares", "traded qty", "traded quantity",
    },
    "price_per_share": {
        "price", "rate", "price per share", "avg price", "trade price",
        "cost price", "avg. price", "average price", "unit price",
        "executed price", "exec price",
    },
}

_BUY_PATTERNS  = re.compile(r"\bbuy\b|^b$", re.I)
_SELL_PATTERNS = re.compile(r"\bsell\b|^s$", re.I)

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent?key={key}"
)

_GEMINI_PROMPT = """You are parsing a brokerage transaction file for Pakistan Stock Exchange (PSX).
Extract every transaction row and return ONLY a valid JSON array — no markdown, no explanation, no code fences.

Each object must have exactly these fields:
- "stock_symbol": string, PSX ticker in uppercase (e.g. "OGDC", "ENGRO", "HBL")
- "date": string in ISO format YYYY-MM-DD
- "transaction_type": exactly "buy" or "sell" (lowercase)
- "shares": positive number (quantity of shares)
- "price_per_share": positive number in PKR

Skip rows that are totals, headers, empty, or missing required fields.

"""


# ── Normalizer ────────────────────────────────────────────────────────────────

def _match_header(col: str) -> Optional[str]:
    """Return the target field name for a column header, or None."""
    normalized = col.strip().lower().replace("_", " ").replace("-", " ")
    for field, synonyms in _SYNONYMS.items():
        if normalized in synonyms:
            return field
    return None


def _normalize_type(value: str) -> Optional[str]:
    v = str(value).strip()
    if _BUY_PATTERNS.search(v):
        return "buy"
    if _SELL_PATTERNS.search(v):
        return "sell"
    return None


def _normalize_date(value: str) -> Optional[str]:
    try:
        return dateutil_parser.parse(str(value).strip(), dayfirst=True).date().isoformat()
    except Exception:
        return None


def _normalize_number(value: str) -> Optional[str]:
    """Strip commas/currency symbols and return a numeric string."""
    cleaned = re.sub(r"[^\d.]", "", str(value).replace(",", ""))
    return cleaned if cleaned else None


def run_normalizer(rows: list[list[str]]) -> tuple[list[dict], int]:
    """
    Map raw CSV/Excel rows to transaction dicts using header synonyms.
    Returns (parsed_rows, mapped_column_count).
    """
    if not rows:
        return [], 0

    # Find header row: first row where ≥2 cells match known synonyms
    header_idx = 0
    col_map: dict[str, int] = {}
    for i, row in enumerate(rows[:10]):
        mapping = {}
        for j, cell in enumerate(row):
            field = _match_header(str(cell))
            if field and field not in mapping:
                mapping[field] = j
        if len(mapping) >= 2:
            header_idx = i
            col_map = mapping
            break

    if len(col_map) < 2:
        return [], 0

    results = []
    for row in rows[header_idx + 1:]:
        if not any(str(c).strip() for c in row):
            continue  # skip blank rows

        def get(field):
            idx = col_map.get(field)
            return str(row[idx]).strip() if idx is not None and idx < len(row) else ""

        symbol = get("stock_symbol").upper()
        date   = _normalize_date(get("date")) if "date" in col_map else None
        ttype  = _normalize_type(get("transaction_type")) if "transaction_type" in col_map else None
        shares = _normalize_number(get("shares")) if "shares" in col_map else None
        price  = _normalize_number(get("price_per_share")) if "price_per_share" in col_map else None

        if not symbol:
            continue

        results.append({
            "stock_symbol":      symbol or None,
            "date":              date,
            "transaction_type":  ttype,
            "shares":            shares,
            "price_per_share":   price,
        })

    return results, len(col_map)


# ── File reading ──────────────────────────────────────────────────────────────

def read_csv(file_bytes: bytes) -> list[list[str]]:
    text = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    return [row for row in reader]


def read_xlsx(file_bytes: bytes) -> list[list[str]]:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active
    rows = []
    for row in ws.iter_rows(values_only=True):
        rows.append([str(c) if c is not None else "" for c in row])
    wb.close()
    return rows


_DATE_LINE = re.compile(r'^(\d{1,2}/\d{1,2}/\d{4})\s+(.*)')


def read_pdf(file_bytes: bytes) -> list[list[str]]:
    """
    Extract rows from a PDF using pdfplumber.
    First tries table extraction (works when the PDF has visible grid lines).
    Falls back to text-line extraction for PDFs with positioned text but no borders
    (e.g. Finqalab Cash Book Reports), returning [date, rest_of_line] pairs.
    """
    import pdfplumber
    rows = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                for row in table:
                    rows.append([str(c).strip() if c else "" for c in row])

    if rows:
        return rows

    # No table borders found — extract raw text and split into lines
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                m = _DATE_LINE.match(line)
                if m:
                    rows.append([m.group(1), m.group(2)])
                else:
                    rows.append(['', line])
    return rows


def rows_to_text(rows: list[list[str]]) -> str:
    return "\n".join(",".join(row) for row in rows[:500])


# ── Gemini Flash ──────────────────────────────────────────────────────────────

def _call_gemini(parts: list[dict], api_key: str) -> list[dict]:
    """Send content parts to Gemini and parse the JSON array response."""
    resp = requests.post(
        _GEMINI_URL.format(key=api_key),
        json={"contents": [{"parts": parts}]},
        timeout=40,
    )
    resp.raise_for_status()

    raw_text = (
        resp.json()
        .get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )

    # Strip markdown fences if Gemini wraps the JSON
    raw_text = re.sub(r"```(?:json)?", "", raw_text).strip().strip("`").strip()

    # Extract the JSON array even if there's surrounding text
    match = re.search(r"\[.*\]", raw_text, re.DOTALL)
    if not match:
        logger.warning("Gemini returned no JSON array: %s", raw_text[:200])
        return []

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        logger.warning("Gemini JSON parse failed: %s", raw_text[:200])
        return []

    return data if isinstance(data, list) else []


def parse_with_gemini_text(raw_text: str, api_key: str) -> list[dict]:
    parts = [{"text": _GEMINI_PROMPT + raw_text[:15000]}]
    return _call_gemini(parts, api_key)


def parse_with_gemini_image(image_bytes: bytes, mime_type: str, api_key: str) -> list[dict]:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    parts = [
        {"text": _GEMINI_PROMPT + "The image contains a table of transactions. Extract all rows."},
        {"inline_data": {"mime_type": mime_type, "data": b64}},
    ]
    return _call_gemini(parts, api_key)


# ── Normalise Gemini output to match our schema ───────────────────────────────

def _normalise_gemini_row(row: dict) -> dict:
    """Coerce Gemini's output into the same shape as the normalizer output."""
    symbol = str(row.get("stock_symbol") or "").strip().upper()
    raw_date = str(row.get("date") or "").strip()
    date = _normalize_date(raw_date) if raw_date else None
    ttype = _normalize_type(str(row.get("transaction_type") or ""))
    shares = _normalize_number(str(row.get("shares") or ""))
    price  = _normalize_number(str(row.get("price_per_share") or ""))
    return {
        "stock_symbol":     symbol or None,
        "date":             date,
        "transaction_type": ttype,
        "shares":           shares,
        "price_per_share":  price,
    }


# ── Main entry point ──────────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".pdf", ".png", ".jpg", ".jpeg"}
IMAGE_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
MAX_CSV_BYTES   = 5 * 1024 * 1024   # 5 MB
MAX_IMAGE_BYTES = 4 * 1024 * 1024   # 4 MB

# Matches descriptions like:
#   "EFERT BUY 9 @ 219.5000, BRK = ..."
#   "FATIMA SELL 71 @ 131.9800, BRK = ..."
_CASHBOOK_TX = re.compile(
    r'^([A-Z]{2,10})\s+(BUY|SELL)\s+([\d]+(?:\.\d+)?)\s+@\s+([\d.]+)',
    re.IGNORECASE,
)


def run_cashbook_normalizer(rows: list[list[str]]) -> list[dict]:
    """
    Parse broker Cash Book Report format (Finqalab / similar):
    Columns: Settlement Date | Description | Amount | Balance

    Transaction rows embed the data in Description:
      "EFERT BUY 9 @ 219.5000, BRK = 4.94, CVT = .00, WHT = .00, FED = .74"

    Non-transaction rows (margin entries, payments, charges) are silently skipped.
    """
    results = []
    for row in rows:
        if len(row) < 2:
            continue
        date_str = row[0].strip()
        desc     = row[1].strip()

        m = _CASHBOOK_TX.match(desc)
        if not m:
            continue

        date = _normalize_date(date_str)
        if not date:
            continue

        try:
            price = str(round(float(m.group(4)), 2))
        except ValueError:
            price = m.group(4)

        results.append({
            "stock_symbol":     m.group(1).upper(),
            "date":             date,
            "transaction_type": m.group(2).lower(),
            "shares":           m.group(3),
            "price_per_share":  price,
        })
    return results


def _detect_cashbook_format(rows: list[list[str]]) -> bool:
    """Return True if the rows look like a Cash Book Report (Description-embedded format)."""
    for row in rows[:30]:
        if len(row) >= 2 and _CASHBOOK_TX.match(row[1].strip()):
            return True
    return False


def parse_import_file(
    file_bytes: bytes,
    filename: str,
    api_key: str = "",
) -> tuple[list[dict], str | None]:
    """
    Parse an uploaded file into a list of raw transaction dicts.

    Returns:
        (rows, error_message)
        On success: (list_of_dicts, None)
        On failure: ([], "human-readable error")

    Each dict has keys: stock_symbol, date, transaction_type, shares, price_per_share.
    Values may be None if the source didn't provide them — caller validates.
    """
    import os
    ext = os.path.splitext(filename.lower())[1]

    if ext not in SUPPORTED_EXTENSIONS:
        return [], f"Unsupported file type '{ext}'. Allowed: .csv, .xlsx, .pdf, .png, .jpg, .jpeg"

    if not file_bytes:
        return [], "The uploaded file is empty."

    # ── Image path: always use Gemini vision ─────────────────────────────────
    if ext in IMAGE_MIME:
        if len(file_bytes) > MAX_IMAGE_BYTES:
            return [], "Image file too large. Maximum size is 4 MB."
        if not api_key:
            return [], (
                "Image import requires GEMINI_API_KEY. "
                "Get a free key at aistudio.google.com and set it in your .env."
            )
        try:
            raw = parse_with_gemini_image(file_bytes, IMAGE_MIME[ext], api_key)
            rows = [_normalise_gemini_row(r) for r in raw]
            return rows, None
        except Exception:
            logger.exception("Gemini image parse failed for %s", filename)
            return [], "AI could not read this image. Try exporting a CSV from your broker instead."

    # ── PDF path ──────────────────────────────────────────────────────────────
    if ext == ".pdf":
        if len(file_bytes) > MAX_CSV_BYTES:
            return [], "PDF file too large. Maximum size is 5 MB."
        try:
            rows_raw = read_pdf(file_bytes)
        except Exception:
            logger.exception("Failed to read PDF %s", filename)
            return [], "Could not read this PDF. Make sure it is not password-protected."

        if not rows_raw:
            return [], "No text could be extracted from this PDF. If it is a scanned document, try uploading a JPG/PNG screenshot instead."

        # Try cash book format first (Finqalab / similar brokers)
        if _detect_cashbook_format(rows_raw):
            logger.info("Cash Book format detected for %s", filename)
            results = run_cashbook_normalizer(rows_raw)
            if results:
                return results, None

        # Try standard normalizer (column-header mapping)
        normalizer_rows, mapped_cols = run_normalizer(rows_raw)
        if mapped_cols >= 3:
            logger.info("Normalizer succeeded for PDF %s (%d cols mapped)", filename, mapped_cols)
            return normalizer_rows, None

        # Fall back to Gemini with the raw text
        if not api_key:
            return [], (
                "Could not detect the column format in this PDF. "
                "Set GEMINI_API_KEY in your .env for automatic detection."
            )

        logger.info("Falling back to Gemini for PDF %s", filename)
        try:
            raw = parse_with_gemini_text(rows_to_text(rows_raw), api_key)
            return [_normalise_gemini_row(r) for r in raw], None
        except Exception:
            logger.exception("Gemini text parse failed for PDF %s", filename)
            return [], "AI could not parse this PDF. Try exporting a CSV from your broker instead."

    # ── CSV / Excel path ──────────────────────────────────────────────────────
    if len(file_bytes) > MAX_CSV_BYTES:
        return [], "File too large. Maximum size is 5 MB for CSV/Excel files."

    try:
        if ext == ".csv":
            rows_raw = read_csv(file_bytes)
        else:
            rows_raw = read_xlsx(file_bytes)
    except Exception:
        logger.exception("Failed to read file %s", filename)
        return [], "Could not read this file. Make sure it is a valid CSV or Excel file."

    if not rows_raw or all(not any(c.strip() for c in r) for r in rows_raw):
        return [], "The file is empty or contains no data."

    # Try normalizer first (free, fast)
    normalizer_rows, mapped_cols = run_normalizer(rows_raw)
    if mapped_cols >= 3:
        logger.info("Normalizer succeeded for %s (%d cols mapped)", filename, mapped_cols)
        return normalizer_rows, None

    # Normalizer couldn't map enough columns — try Gemini
    if not api_key:
        return [], (
            "Could not automatically detect column format. "
            "Rename your columns to: symbol, date, type, shares, price — "
            "or set GEMINI_API_KEY in your .env for automatic detection."
        )

    logger.info("Normalizer mapped %d cols for %s — falling back to Gemini", mapped_cols, filename)
    try:
        raw = parse_with_gemini_text(rows_to_text(rows_raw), api_key)
        rows = [_normalise_gemini_row(r) for r in raw]
        return rows, None
    except Exception:
        logger.exception("Gemini text parse failed for %s", filename)
        return [], "AI could not parse this file. Try renaming columns to: symbol, date, type, shares, price."
