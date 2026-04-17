import requests, json
from bs4 import BeautifulSoup
from datetime import datetime


SYMBOLS_URL = "https://dps.psx.com.pk/symbols"
EOD_URL = "https://dps.psx.com.pk/timeseries/eod/{symbol}"
KMIALLSHR_URL = "https://dps.psx.com.pk/indices/KMIALLSHR"
SCSTRADE_DIVIDENDS_URL = "https://www.scstrade.com/MarketStatistics/MS_xDates.aspx/chartact"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:143.0) Gecko/20100101 Firefox/143.0",
}

def fetch_dividends(symbol, company_name):
    """Fetch dividend history from scstrade.com"""
    headers = {
        **HEADERS,
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.scstrade.com/MarketStatistics/MS_xDates.aspx",
        "Origin": "https://www.scstrade.com",
    }

    payload = {
        "par": f"{symbol} - {company_name}",
        "_search": False,
        "nd": 1776421917234,
        "rows": "100",
        "page": 1,
        "sidx": "",
        "sord": "asc"
    }

    response = requests.post(
        SCSTRADE_DIVIDENDS_URL,
        headers=headers,
        data=json.dumps(payload)
    )

    print(f"Status: {response.status_code}")
    data = response.json()
    return data.get("d", [])

def fetch_shariah_symbols():
    """Fetch all KMI All Share (Shariah compliant) symbols"""
    response = requests.get(KMIALLSHR_URL, headers=HEADERS)
    soup = BeautifulSoup(response.text, 'html.parser')

    symbols = []
    rows = soup.select('tbody.tbl__body tr')
    for row in rows:
        symbol_td = row.find('td', {'data-order': True})
        if symbol_td:
            symbols.append(symbol_td['data-order'])

    return symbols


def fetch_all_symbols():
    """Fetch all symbols from PSX with metadata"""
    response = requests.get(SYMBOLS_URL, headers=HEADERS)
    return response.json()


def fetch_eod_prices(symbol):
    """Fetch EOD price history for a symbol"""
    url = EOD_URL.format(symbol=symbol)
    try:
        response = requests.get(url, headers=HEADERS)
        if not response.text.strip():
            print(f"  Warning: Empty response for {symbol}")
            return []
        data = response.json()
        return data.get("data", [])
    except Exception as e:
        print(f"  Warning: Failed to fetch {symbol} - {e}")
        return []


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


def fetch_payouts(symbol):
    headers = {
        **HEADERS,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://dps.psx.com.pk/payouts/",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }

    data = f"symbol={symbol}&count=25&offset=0"
    response = requests.post(
        "https://dps.psx.com.pk/payouts",
        headers=headers,
        data=data
    )
    # Print raw HTML so we can see the structure
    print(response.text)




if __name__ == "__main__":
    print("Testing dividends for MEBL...")
    dividends = fetch_dividends("MEBL", "Meezan Bank Ltd.")
    print(f"Total records: {len(dividends)}")
    print("\nFirst 3:")
    for d in dividends[:3]:
        print(d)
    print("\nLast 3:")
    for d in dividends[-3:]:
        print(d)