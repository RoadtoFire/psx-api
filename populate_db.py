import os
import django

# Setup Django environment before importing models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from stocks.models import Stock, DailyPrice
from scraper import fetch_shariah_symbols, fetch_all_symbols, fetch_eod_prices, parse_eod_row


def populate_stocks():
    """Fetch Shariah symbols and save to Stock table"""
    print("Fetching Shariah compliant symbols...")
    shariah_symbols = fetch_shariah_symbols()
    shariah_set = set(shariah_symbols)

    print("Fetching full symbol metadata...")
    all_symbols = fetch_all_symbols()
    all_map = {s['symbol']: s for s in all_symbols}

    created_count = 0
    skipped_count = 0

    for symbol in shariah_symbols:
        meta = all_map.get(symbol, {})
        # Skip debt instruments and ETFs
        if meta.get('isDebt') or meta.get('isETF'):
            skipped_count += 1
            continue

        stock, created = Stock.objects.get_or_create(
            symbol=symbol,
            defaults={
                'name': meta.get('name', ''),
                'sector': meta.get('sectorName', ''),
            }
        )
        if created:
            created_count += 1
            print(f"  Created: {symbol}")

    print(f"\nDone. Created: {created_count}, Skipped: {skipped_count}")


def populate_indices():
    """Populate index list and their price history"""
    indices = [
        {"symbol": "KSE100", "name": "KSE 100 Index"},
        {"symbol": "KMI30", "name": "KMI 30 Shariah Index"},
        {"symbol": "KMIALLSHR", "name": "KMI All Shares Shariah Index"},
    ]

    from stocks.models import Index, IndexDailyPrice

    for idx in indices:
        index, created = Index.objects.get_or_create(
            symbol=idx['symbol'],
            defaults={'name': idx['name']}
        )
        print(f"{'Created' if created else 'Exists'}: {idx['symbol']}")

        rows = fetch_eod_prices(idx['symbol'])
        prices_to_create = []
        for row in rows:
            parsed = parse_eod_row(row)
            prices_to_create.append(
                IndexDailyPrice(
                    index=index,
                    date=parsed['date'],
                    open=parsed['open'],
                    close=parsed['close'],
                    volume=parsed['volume'],
                )
            )

        IndexDailyPrice.objects.bulk_create(
            prices_to_create,
            ignore_conflicts=True
        )
        print(f"  Saved {len(prices_to_create)} price records")


def populate_prices(symbol=None, limit=None):
    """Fetch EOD prices and save to DailyPrice table"""
    if symbol:
        stocks = Stock.objects.filter(symbol=symbol)
    else:
        stocks = Stock.objects.all()

    if limit:
        stocks = stocks[:limit]

    total_stocks = stocks.count()

    for i, stock in enumerate(stocks, 1):
        print(f"[{i}/{total_stocks}] Fetching prices for {stock.symbol}...")
        rows = fetch_eod_prices(stock.symbol)

        prices_to_create = []
        for row in rows:
            parsed = parse_eod_row(row)
            prices_to_create.append(
                DailyPrice(
                    stock=stock,
                    date=parsed['date'],
                    open=parsed['open'],
                    close=parsed['close'],
                    volume=parsed['volume'],
                )
            )

        # bulk_create is much faster than saving one by one
        # ignore_conflicts skips duplicates instead of crashing
        DailyPrice.objects.bulk_create(
            prices_to_create,
            ignore_conflicts=True
        )
        print(f"  Saved {len(prices_to_create)} price records")


    


if __name__ == "__main__":
    print("=== Step 1: Populate Stocks ===")
    populate_stocks()

    print("\n=== Step 2: Populate Prices (MEBL only for now) ===")
    populate_prices(symbol='MEBL')

    print("\n=== Step 3: Populate Indices ===")
    populate_indices()