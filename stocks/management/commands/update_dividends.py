import io
import time
import traceback
from django.core.management.base import BaseCommand
from stocks.models import Stock, Dividend, CronLog
from dividend_scraper import fetch_dividends, parse_dividend


class Command(BaseCommand):
    help = 'Check for newly announced dividends'

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
                name='update_dividends',
                success=success,
                output=out.getvalue()[:5000],
                duration_seconds=round(_time.time() - start, 2),
            )
        self.stdout.write(out.getvalue())

    def _run(self, out):
        new_dividends = 0

        for stock in Stock.objects.filter(is_active=True):
            entries = fetch_dividends(stock.symbol)
            if not entries:
                continue

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

        out.write(f'New dividends found: {new_dividends}\n')
