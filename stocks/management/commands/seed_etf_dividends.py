"""
One-time seed: manually confirmed annual distributions for Meezan ETFs.
Ex-dates set to 30 Jun of each year (Pakistan fiscal year end) — update exact
dates via Django admin once you have them.

Usage:
    python manage.py seed_etf_dividends
"""
from datetime import date
from django.core.management.base import BaseCommand
from stocks.models import Stock, Dividend

ETF_DIVIDENDS = [
    # (symbol, ex_date, cash_amount_per_share)
    ('MIIETF',  date(2024, 6, 30), 0.50),
    ('MIIETF',  date(2025, 6, 30), 2.25),
    ('MIIETF',  date(2026, 6, 30), 0.75),

    ('MZNPETF', date(2021, 6, 30), 1.25),
    # 2022 and 2023: no distribution — not recorded
    ('MZNPETF', date(2024, 6, 30), 1.00),
    ('MZNPETF', date(2025, 6, 30), 2.25),
    ('MZNPETF', date(2026, 6, 30), 3.50),
]


class Command(BaseCommand):
    help = 'Seed manually confirmed annual dividend distributions for MIIETF and MZNPETF'

    def handle(self, *args, **options):
        created = 0
        skipped = 0

        for symbol, ex_date, amount in ETF_DIVIDENDS:
            try:
                stock = Stock.objects.get(symbol=symbol, is_active=True)
            except Stock.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f'  {symbol} not found in DB — run add_etfs first'
                ))
                continue

            _, was_created = Dividend.objects.get_or_create(
                stock=stock,
                ex_date=ex_date,
                defaults={
                    'dividend_type': 'cash',
                    'cash_amount': amount,
                    'bonus_ratio': None,
                    'raw_dividend': f'Rs. {amount}/share (manually entered)',
                    'raw_bonus': '',
                },
            )
            if was_created:
                self.stdout.write(f'  ✓ {symbol}  {ex_date}  Rs. {amount}/share')
                created += 1
            else:
                self.stdout.write(f'  — {symbol}  {ex_date}  already exists')
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. Created: {created}  Already existed: {skipped}'
        ))
        self.stdout.write(
            '  Note: ex_dates are set to 30 Jun of each year.\n'
            '  Correct exact dates via Django admin → Stocks → Dividends.'
        )
