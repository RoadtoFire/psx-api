import requests
import json

SCSTRADE_URL = "https://www.scstrade.com/MarketStatistics/MS_xDates.aspx/chartact"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:143.0) Gecko/20100101 Firefox/143.0",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.scstrade.com/MarketStatistics/MS_xDates.aspx",
    "Origin": "https://www.scstrade.com",
}


def fetch_dividends(symbol):
    """Fetch full dividend history for a symbol"""
    payload = {
        "par": symbol,
        "_search": False,
        "nd": 1776421917234,
        "rows": "500",
        "page": 1,
        "sidx": "",
        "sord": "asc"
    }
    try:
        response = requests.post(
            SCSTRADE_URL,
            headers=HEADERS,
            data=json.dumps(payload)
        )
        entries = response.json().get("d", [])

        # Filter empty rows
        return [
            e for e in entries
            if e.get("bm_bc_exp") or e.get("bm_dividend") or e.get("bm_bonus")
        ]
    except Exception as e:
        print(f"  Warning: Failed to fetch dividends for {symbol} - {e}")
        return []


def parse_dividend(symbol, entry):
    """Parse a raw dividend entry into a clean dict"""
    from datetime import datetime

    # Parse ex_date
    ex_date = None
    raw_date = entry.get("bm_bc_exp", "").strip()
    if raw_date:
        try:
            ex_date = datetime.strptime(raw_date, "%d %b %Y").strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Parse dividend amount — "70%" → 7.0 (Rs per share, face value Rs 10)
    cash_amount = None
    raw_dividend = entry.get("bm_dividend", "").strip()
    if raw_dividend:
        try:
            # Remove % and any extra text like "(CY15)" or "(F)"
            clean = raw_dividend.replace("%", "").split("(")[0].strip()
            cash_amount = float(clean) / 10  # Convert % to Rs per share
        except ValueError:
            pass

    # Parse bonus ratio — "10%" → 0.10
    bonus_ratio = None
    raw_bonus = entry.get("bm_bonus", "").strip()
    if raw_bonus:
        try:
            clean = raw_bonus.replace("%", "").split()[0].strip()
            bonus_ratio = float(clean) / 100
        except ValueError:
            pass

    return {
        "symbol": symbol,
        "ex_date": ex_date,
        "cash_amount": cash_amount,
        "bonus_ratio": bonus_ratio,
        "raw_dividend": raw_dividend,
        "raw_bonus": raw_bonus,
    }


if __name__ == "__main__":
    # Test parsing for MEBL
    print("Testing dividend fetch and parsing for MEBL...")
    entries = fetch_dividends("MEBL")
    print(f"Total records: {len(entries)}")

    print("\nParsed dividends:")
    for e in entries[:5]:
        parsed = parse_dividend("MEBL", e)
        print(parsed)