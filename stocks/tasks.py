from celery import shared_task
from datetime import date
import time


@shared_task
def update_daily_prices():
    """Fetch and save latest prices for all active stocks"""
    from stocks.models import Stock, DailyPrice
    from scraper import fetch_eod_prices, parse_eod_row

    stocks = Stock.objects.filter(is_active=True)
    updated = 0
    skipped = 0

    for stock in stocks:
        rows = fetch_eod_prices(stock.symbol)
        if not rows:
            skipped += 1
            continue

        # Only process last 3 rows — daily update needs recent data only
        recent_rows = rows[:3]
        prices_to_create = []
        for row in recent_rows:
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

        DailyPrice.objects.bulk_create(
            prices_to_create,
            ignore_conflicts=True
        )
        updated += 1
        time.sleep(0.2)

    return f"Updated: {updated}, Skipped: {skipped}"


@shared_task
def update_index_prices():
    """Fetch and save latest prices for indices"""
    from stocks.models import Index, IndexDailyPrice
    from scraper import fetch_eod_prices, parse_eod_row

    indices = Index.objects.all()

    for index in indices:
        rows = fetch_eod_prices(index.symbol)
        if not rows:
            continue

        recent_rows = rows[:3]
        prices_to_create = []
        for row in recent_rows:
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

    return "Index prices updated"


@shared_task
def update_dividends():
    """Check for newly announced dividends"""
    from stocks.models import Stock, Dividend
    from dividend_scraper import fetch_dividends, parse_dividend

    stocks = Stock.objects.filter(is_active=True)
    new_dividends = 0

    for stock in stocks:
        entries = fetch_dividends(stock.symbol)
        if not entries:
            continue

        # Only check latest 3 announcements
        for entry in entries[:3]:
            parsed = parse_dividend(stock.symbol, entry)
            if not parsed['ex_date']:
                continue

            if parsed['cash_amount'] and parsed['bonus_ratio']:
                div_type = 'mixed'
            elif parsed['cash_amount']:
                div_type = 'cash'
            elif parsed['bonus_ratio']:
                div_type = 'bonus'
            else:
                continue

            _, created = Dividend.objects.get_or_create(
                stock=stock,
                ex_date=parsed['ex_date'],
                defaults={
                    'dividend_type': div_type,
                    'cash_amount': parsed['cash_amount'],
                    'bonus_ratio': parsed['bonus_ratio'],
                    'raw_dividend': parsed['raw_dividend'],
                    'raw_bonus': parsed['raw_bonus'],
                }
            )
            if created:
                new_dividends += 1

        time.sleep(0.2)

    return f"New dividends found: {new_dividends}"