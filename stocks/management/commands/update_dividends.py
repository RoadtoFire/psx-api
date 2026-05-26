import time
from django.core.management.base import BaseCommand
from stocks.models import Stock, Dividend
from dividend_scraper import fetch_dividends, parse_dividend


class Command(BaseCommand):
    help = 'Check for newly announced dividends'

    def handle(self, *args, **options):
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

        self.stdout.write(f'New dividends found: {new_dividends}')
