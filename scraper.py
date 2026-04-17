import requests
from datetime import datetime
from bs4 import BeautifulSoup


SYMBOLS_URL = "https://dps.psx.com.pk/symbols"
EOD_URL = "https://dps.psx.com.pk/timeseries/eod/{symbol}"
KMIALLSHR_URL = "https://dps.psx.com.pk/indices/KMIALLSHR"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def fetch_shariah_symbols():
    """Fetch all shariah compliant stocks from PSX"""
    response = requests.get(KMIALLSHR_URL, headers=HEADERS)
    soup = BeautifulSoup(response.text, "html.parser")

    symbols = []
    rows = soup.select('tbody.tbl__body tr')
    for row in rows:
        symbol_td = row.find("td", {"data-order": True})
        if symbol_td:
            symbols.append(symbol_td["data-order"])
    
    return symbols

def fetch_all_symbols():
    "Fetch all symbols with their metadata from PSX"
    response = requests.get(SYMBOLS_URL, headers=HEADERS)
    return response.json()


def fetch_eod_prices(symbol):
    """Fetch EOD price history for a symbol"""
    url = EOD_URL.format(symbol=symbol)
    response = requests.get(url, headers=HEADERS)
    data = response.json()
    return data.get("data", [])


def parse_eod_row(row):
    """Convert [timestamp, close, volume, open] to a dict"""
    timestamp, close, volume, open_price = row
    date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
    return {
        "date": date,
        "open": open_price,
        "close": close,
        "volume": volume,
    }


if __name__ == "__main__":
    # Test 1: fetch Shariah symbols
    print("Fetching Shariah compliant symbols...")
    shariah = fetch_shariah_symbols()
    print(f"Total Shariah compliant stocks: {len(shariah)}")
    print(f"First 5: {shariah[:5]}")

    # Test 2: cross reference with full symbols list
    print("\nFetching full PSX symbols list...")
    all_symbols = fetch_all_symbols()
    all_map = {s['symbol']: s for s in all_symbols}
    
    print("\nSample Shariah stocks with metadata:")
    for sym in shariah[:5]:
        meta = all_map.get(sym, {})
        print(f"{sym} - {meta.get('name')} - {meta.get('sectorName')}")