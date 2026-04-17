import os
import django
import requests
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from stocks.models import Stock

def fetch_tv_logo(symbol):
    url = f"https://symbol-search.tradingview.com/symbol_search/v3/?text={symbol}&hl=1&exchange=PSX&lang=en&search_type=undefined&domain=production"
    headers = {
        "Referer": "https://www.tradingview.com/",
        "Origin": "https://www.tradingview.com",
        "User-Agent": "Mozilla/5.0"
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()
        symbols = data.get('symbols', [])
        # Find PSX match
        for s in symbols:
            if s.get('exchange') == 'PSX':
                return s.get('logoid')
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
    return None

def populate_logos():
    stocks = Stock.objects.filter(is_active=True, tv_logo_id__isnull=True)
    total = stocks.count()
    print(f"Fetching logos for {total} stocks...")

    for i, stock in enumerate(stocks):
        logoid = fetch_tv_logo(stock.symbol)
        if logoid:
            stock.tv_logo_id = logoid
            stock.save()
            print(f"[{i+1}/{total}] {stock.symbol} → {logoid}")
        else:
            print(f"[{i+1}/{total}] {stock.symbol} → no logo found")
        time.sleep(0.3)  # be polite

    print("Done!")

if __name__ == '__main__':
    populate_logos()