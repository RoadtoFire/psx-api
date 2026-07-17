import io
import time
import traceback
from django.core.management.base import BaseCommand
from stocks.models import Stock, DailyPrice, Index, IndexDailyPrice, CronLog
from scraper import fetch_eod_prices, parse_eod_row


class Command(BaseCommand):
    help = 'Fetch and save latest EOD prices for all active stocks and indices'

    def handle(self, *args, **options):
        import time as _time
        out = io.StringIO()
        start = _time.time()
        success = True
        try:
            self._run(out)
        except Exception:
            out.write(traceback.format_exc())
            success = False
        finally:
            CronLog.objects.create(
                name='update_prices',
                success=success,
                output=out.getvalue()[:5000],
                duration_seconds=round(_time.time() - start, 2),
            )
        self.stdout.write(out.getvalue())

    def _run(self, out):
        updated = 0
        skipped = 0

        for stock in Stock.objects.filter(is_active=True):
            rows = fetch_eod_prices(stock.symbol)
            if not rows:
                skipped += 1
                continue

            prices_to_create = []
            for row in rows[:3]:
                parsed = parse_eod_row(row)
                prices_to_create.append(DailyPrice(
                    stock=stock,
                    date=parsed['date'],
                    open=parsed['open'],
                    close=parsed['close'],
                    volume=parsed['volume'],
                ))

            DailyPrice.objects.bulk_create(prices_to_create, ignore_conflicts=True)
            updated += 1
            time.sleep(0.2)

        out.write(f'Stocks: updated={updated}, skipped={skipped}\n')

        for index in Index.objects.all():
            rows = fetch_eod_prices(index.symbol)
            if not rows:
                continue

            prices_to_create = []
            for row in rows[:3]:
                parsed = parse_eod_row(row)
                prices_to_create.append(IndexDailyPrice(
                    index=index,
                    date=parsed['date'],
                    open=parsed['open'],
                    close=parsed['close'],
                    volume=parsed['volume'],
                ))

            IndexDailyPrice.objects.bulk_create(prices_to_create, ignore_conflicts=True)

        out.write('Index prices updated\n')
