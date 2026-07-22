"""
One-time portfolio import from a broker CSV export.

Usage:
    python manage.py import_portfolio <username_or_email> <csv_file_path>

CSV format (exported from Amanat or broker):
    Type, Transaction Date, Stock Symbol, Number of Shares,
    Price per Share, Dividend per Share, Commission/Taxes, Total Value, Note

- buy / sell rows are imported as Transactions.
- dividend rows are skipped — they are auto-calculated from scraped stock data.
- Rows with a stock symbol not in the DB are reported and skipped.
- Existing identical transactions are skipped (duplicate check on date+stock+type+shares+price).
"""
import csv
import sys
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from dateutil import parser as dateutil_parser
from transactions.models import Portfolio, Transaction
from stocks.models import Stock

User = get_user_model()


class Command(BaseCommand):
    help = 'Import buy/sell transactions from a CSV file into a user\'s portfolio'

    def add_arguments(self, parser):
        parser.add_argument('user', help='Username or email of the target user')
        parser.add_argument('csv_file', help='Path to the CSV file')

    def handle(self, *args, **options):
        # ── Find user ─────────────────────────────────────────────────────────
        identifier = options['user']
        try:
            user = User.objects.get(username=identifier)
        except User.DoesNotExist:
            try:
                user = User.objects.get(email__iexact=identifier)
            except User.DoesNotExist:
                raise CommandError(f"No user found with username or email '{identifier}'")

        self.stdout.write(f"User: {user.email} (id={user.id})")

        portfolio, created = Portfolio.objects.get_or_create(
            user=user,
            defaults={'name': 'My Portfolio'},
        )
        self.stdout.write(f"Portfolio: {'created' if created else 'existing'} (id={portfolio.id})\n")

        # ── Read CSV ──────────────────────────────────────────────────────────
        csv_path = options['csv_file']
        try:
            f = open(csv_path, newline='', encoding='utf-8-sig')
        except FileNotFoundError:
            raise CommandError(f"File not found: {csv_path}")

        reader = csv.DictReader(f)

        imported = 0
        skipped_dividends = 0
        skipped_no_stock = []
        skipped_errors = []
        duplicates = 0

        for i, row in enumerate(reader, start=2):   # row 1 = header
            tx_type = (row.get('Type') or '').strip().lower()
            symbol   = (row.get('Stock Symbol') or '').strip().upper()
            date_str = (row.get('Transaction Date') or '').strip()
            shares_str = (row.get('Number of Shares') or '').strip().replace(',', '')
            price_str  = (row.get('Price per Share') or '').strip().replace(',', '')
            note     = (row.get('Note') or '').strip()

            # Skip dividend rows
            if tx_type == 'dividend':
                skipped_dividends += 1
                continue

            if tx_type not in ('buy', 'sell'):
                skipped_errors.append((i, symbol, f"Unknown type '{tx_type}'"))
                continue

            # Parse date
            try:
                date = dateutil_parser.parse(date_str, dayfirst=False).date()
            except Exception:
                skipped_errors.append((i, symbol, f"Cannot parse date '{date_str}'"))
                continue

            # Parse shares
            try:
                shares = Decimal(shares_str)
            except InvalidOperation:
                skipped_errors.append((i, symbol, f"Cannot parse shares '{shares_str}'"))
                continue

            # Parse price (0 is allowed — e.g. stock splits)
            try:
                price = Decimal(price_str) if price_str else Decimal('0')
            except InvalidOperation:
                skipped_errors.append((i, symbol, f"Cannot parse price '{price_str}'"))
                continue

            # Look up stock
            try:
                stock = Stock.objects.get(symbol=symbol, is_active=True)
            except Stock.DoesNotExist:
                skipped_no_stock.append((i, symbol, date_str))
                continue

            # Duplicate check
            exists = Transaction.objects.filter(
                portfolio=portfolio,
                stock=stock,
                transaction_type=tx_type,
                date=date,
                shares=shares,
                price_per_share=price,
            ).exists()
            if exists:
                duplicates += 1
                continue

            # Create
            label = f"[{price_str}]" if price > 0 else "[SPLIT/0-price]"
            Transaction.objects.create(
                portfolio=portfolio,
                stock=stock,
                transaction_type=tx_type,
                date=date,
                shares=shares,
                price_per_share=price,
            )
            imported += 1
            self.stdout.write(f"  ✓ {tx_type.upper():4}  {symbol:8}  {date}  {shares} shares @ {price}  {label}")

        f.close()

        # ── Summary ───────────────────────────────────────────────────────────
        self.stdout.write(f"\n{'─'*50}")
        self.stdout.write(self.style.SUCCESS(f"Imported:          {imported}"))
        if duplicates:
            self.stdout.write(f"Skipped duplicates: {duplicates}")
        if skipped_dividends:
            self.stdout.write(
                f"Skipped dividends:  {skipped_dividends}  "
                "(dividends are auto-calculated from scraped data — no action needed)"
            )
        if skipped_no_stock:
            self.stdout.write(self.style.WARNING(f"\nStocks not found in DB ({len(skipped_no_stock)}):"))
            for row_num, sym, date_s in skipped_no_stock:
                self.stdout.write(f"  row {row_num}: {sym}  ({date_s})")
            self.stdout.write(
                "  → These stocks may not be KMI-listed or may use a different ticker.\n"
                "    Check the symbol on PSX and add via the admin if needed."
            )
        if skipped_errors:
            self.stdout.write(self.style.ERROR(f"\nErrors ({len(skipped_errors)}):"))
            for row_num, sym, reason in skipped_errors:
                self.stdout.write(f"  row {row_num}: {sym}  — {reason}")
