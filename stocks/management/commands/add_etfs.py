"""
Add Meezan Islamic ETFs to the stock universe and mark them as fully Shariah-compliant
(no purification required — the fund managers purify on behalf of investors).

Usage:
    python manage.py add_etfs

Safe to run multiple times (uses get_or_create).
"""
from datetime import date
from django.core.management.base import BaseCommand
from stocks.models import Stock, PurificationRatio

ETFS = [
    {
        'symbol': 'MIIETF',
        'name': 'Meezan Islamic Income ETF',
        'sector': 'ETF',
        'launch_date': date(2014, 1, 1),
    },
    {
        'symbol': 'MZNPETF',
        'name': 'Meezan Pakistan ETF',
        'sector': 'ETF',
        'launch_date': date(2020, 1, 1),
    },
]


class Command(BaseCommand):
    help = 'Add Meezan Islamic ETFs and mark them as fully Shariah-compliant (ratio=null)'

    def handle(self, *args, **options):
        for etf in ETFS:
            stock, created = Stock.objects.get_or_create(
                symbol=etf['symbol'],
                defaults={
                    'name': etf['name'],
                    'sector': etf['sector'],
                    'is_active': True,
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created stock: {etf['symbol']} — {etf['name']}"))
            else:
                # Ensure it's active even if it was previously deactivated
                if not stock.is_active:
                    stock.is_active = True
                    stock.save(update_fields=['is_active'])
                    self.stdout.write(f"Re-activated: {etf['symbol']}")
                else:
                    self.stdout.write(f"Already exists: {etf['symbol']}")

            # ratio=None means "fully Islamic institution — skip purification entirely"
            # (distinct from ratio=0 which would mean 0% to purify)
            purif, purif_created = PurificationRatio.objects.get_or_create(
                stock=stock,
                period='Permanent',
                defaults={
                    'ratio': None,
                    'effective_from': etf['launch_date'],
                    'effective_to': None,
                    'source_document': 'Confirmed by fund manager — purification done at fund level',
                },
            )
            if purif_created:
                self.stdout.write(
                    f"  → PurificationRatio set to NULL (Islamic institution, no investor purification needed)"
                )
            else:
                self.stdout.write(f"  → PurificationRatio already set")

        self.stdout.write(self.style.SUCCESS(
            '\nDone. Run `python manage.py update_prices` to fetch current prices for these ETFs.'
        ))
