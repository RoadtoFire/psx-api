"""
Management command: seed_demo

Dev-only. Seeds a demo user with a realistic portfolio into the LOCAL sqlite
database so the frontend can be previewed with data on every page:

  - demo@amanat.local / demo1234 (--staff to also allow /admin)
  - 11 transactions across 6 held symbols, incl. a partial sell and a full exit
  - recent DailyPrice rows so portfolio value / P&L render
  - cash + bonus dividends (incl. one pre-purchase ex-date for eligibility logic)
  - purification ratios (incl. a null-ratio Islamic institution) + one record
  - macro history via backfill_macro + a fully-populated "today" snapshot/warning
  - CronLog rows (incl. one failure) so the admin Scrape Monitor shows data

Safe to re-run: the demo user is deleted and recreated; shared rows use
update_or_create on their natural unique keys. Refuses to run unless
DEBUG=True and the database is sqlite. Never add this to any cron/deploy.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from stocks.models import (
    Stock, DailyPrice, Dividend, PurificationRatio,
    MacroSnapshot, MacroWarning, MacroConfig, CronLog,
)
from stocks.management.commands.update_macro import (
    reserves_signal, oil_signal, real_rate_signal, composite_signal,
)
from transactions.models import Portfolio, Transaction, PurificationRecord

DEMO_EMAIL = 'demo@amanat.local'
DEMO_PASSWORD = 'demo1234'
SEED_MARK = '[seed_demo]'


def months_ago(n):
    return date.today() - timedelta(days=n * 30)


def last_business_days(count):
    """Most recent `count` weekdays, oldest first."""
    days, d = [], date.today()
    while len(days) < count:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return list(reversed(days))


# symbol -> (transactions, latest_close, purification_ratio)
# transaction: (type, months_ago, shares, price)
DEMO_PORTFOLIO = {
    'LUCK': {
        'txns': [('buy', 16, '50', '950.00'), ('buy', 8, '30', '1020.00')],
        'close': '1085.00',
        'ratio': '1.2000',
        'dividends': [(6, 'cash', '12.0000'), (2, 'cash', '10.0000')],
    },
    'MEBL': {
        'txns': [('buy', 15, '200', '210.00')],
        'close': '246.00',
        'ratio': None,  # Islamic institution — no purification
        'dividends': [(5, 'cash', '7.0000'), (1, 'cash', '7.0000')],
    },
    'SYS': {
        'txns': [('buy', 12, '40', '420.00'), ('buy', 5, '25.5', '465.00')],
        'close': '415.00',
        'ratio': '0.8000',
        'dividends': [(4, 'bonus', None)],
    },
    'FFC': {
        'txns': [('buy', 10, '100', '330.00'), ('sell', 3, '40', '365.00')],
        'close': '372.00',
        'ratio': '2.1000',
        'dividends': [(4, 'cash', '15.0000')],
    },
    'OGDC': {
        'txns': [('buy', 9, '150', '205.00')],
        'close': '231.00',
        'ratio': '1.5000',
        'dividends': [(3, 'cash', '5.5000')],
    },
    'HUBC': {
        'txns': [('buy', 7, '120', '125.00')],
        'close': '121.00',
        'ratio': '3.2000',
        # ex-date BEFORE purchase — must be excluded by eligibility logic
        'dividends': [(8, 'cash', '8.0000')],
    },
    'PSO': {  # full exit — zero current holding
        'txns': [('buy', 14, '80', '310.00'), ('sell', 2, '80', '345.00')],
        'close': '338.00',
        'ratio': '1.9000',
        'dividends': [],
    },
}


class Command(BaseCommand):
    help = 'Seed demo user + portfolio + market/macro data into local sqlite (dev only)'

    def add_arguments(self, parser):
        parser.add_argument('--staff', action='store_true',
                            help='Make the demo user staff so /admin is previewable')

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('seed_demo is dev-only (DEBUG must be True)')
        if 'sqlite3' not in settings.DATABASES['default']['ENGINE']:
            raise CommandError('seed_demo only runs against a sqlite database')

        User = get_user_model()

        User.objects.filter(email=DEMO_EMAIL).delete()
        user = User.objects.create_user(
            username='demo', email=DEMO_EMAIL, password=DEMO_PASSWORD,
            filer_status='filer', is_staff=options['staff'],
        )
        portfolio, _ = Portfolio.objects.get_or_create(user=user)
        self.stdout.write(f'Created {DEMO_EMAIL} (staff={options["staff"]})')

        biz_days = last_business_days(5)
        txn_count = div_count = price_count = 0

        for symbol, spec in DEMO_PORTFOLIO.items():
            stock = Stock.objects.filter(symbol=symbol).first()
            if not stock:
                self.stdout.write(self.style.WARNING(f'  {symbol}: not in DB, skipped'))
                continue

            earliest_buy = min(m for _, m, _, _ in spec['txns'])
            for txn_type, m_ago, shares, price in spec['txns']:
                Transaction.objects.create(
                    portfolio=portfolio, stock=stock, transaction_type=txn_type,
                    date=months_ago(m_ago), shares=Decimal(shares),
                    price_per_share=Decimal(price),
                )
                txn_count += 1

            close = Decimal(spec['close'])
            for i, d in enumerate(biz_days):
                drift = Decimal(len(biz_days) - 1 - i) * (close * Decimal('0.004'))
                day_close = close - drift
                DailyPrice.objects.update_or_create(
                    stock=stock, date=d,
                    defaults={
                        'open': day_close * Decimal('0.995'),
                        'close': day_close,
                        'volume': 1_500_000 + i * 120_000,
                    },
                )
                price_count += 1

            for m_ago, div_type, amount in spec['dividends']:
                Dividend.objects.update_or_create(
                    stock=stock, ex_date=months_ago(m_ago),
                    defaults={
                        'dividend_type': div_type,
                        'cash_amount': Decimal(amount) if amount else None,
                        'bonus_ratio': Decimal('0.1000') if div_type == 'bonus' else None,
                    },
                )
                div_count += 1

            PurificationRatio.objects.update_or_create(
                stock=stock, effective_from=months_ago(earliest_buy + 2),
                defaults={
                    'ratio': Decimal(spec['ratio']) if spec['ratio'] else None,
                    'period': 'H1-2026',
                    'source_document': SEED_MARK,
                },
            )

        PurificationRecord.objects.create(
            portfolio=portfolio, purified_up_to_date=months_ago(6),
            amount_purified=Decimal('450.00'),
        )

        self.stdout.write('Backfilling macro history (offline-safe)…')
        call_command('backfill_macro')
        self._seed_today_macro()
        self._seed_cron_logs()

        self.stdout.write(self.style.SUCCESS(
            f'Done: {txn_count} transactions, {div_count} dividends, '
            f'{price_count} price rows.\n'
            f'Login: {DEMO_EMAIL} / {DEMO_PASSWORD}'
        ))

    def _seed_today_macro(self):
        today = date.today()
        kibor_6m, cpi, pkr_usd = 12.25, 10.9, 278.6
        forward_pe = 6.1
        earnings_yield = round(100 / forward_pe, 2)
        erp = round(earnings_yield - kibor_6m, 2)
        erp_sig = 'GREEN' if erp > 5 else ('RED' if erp < 0 else 'YELLOW')

        MacroSnapshot.objects.update_or_create(
            date=today,
            defaults={
                'kibor_6m': kibor_6m, 'kibor_1y': round(kibor_6m * 1.05, 2),
                'pkr_usd_rate': pkr_usd, 'kse100_forward_pe': forward_pe,
                'kse100_earnings_yield': earnings_yield, 'market_erp': erp,
                'erp_signal': erp_sig, 'source': 'seed_demo',
            },
        )

        # One GREEN, one RED, one YELLOW sub-signal → composite WATCH
        reserves, imports, brent = 17.8, 5.57, 115.0
        cover = round(reserves / imports, 2)
        real_rate = round(kibor_6m - cpi, 2)
        res_sig, oil_sig, rr_sig = (
            reserves_signal(cover), oil_signal(brent), real_rate_signal(real_rate)
        )
        score, composite = composite_signal(res_sig, oil_sig, rr_sig)
        MacroWarning.objects.update_or_create(
            date=today,
            defaults={
                'sbp_fx_reserves_usd_bn': reserves,
                'monthly_imports_usd_bn': imports,
                'import_cover_months': cover, 'reserves_signal': res_sig,
                'brent_crude_usd': brent, 'oil_signal': oil_sig,
                'cpi_yoy': cpi, 'real_rate': real_rate, 'real_rate_signal': rr_sig,
                'macro_stress_score': score, 'composite_signal': composite,
            },
        )

        config = MacroConfig.get()
        config.kse100_forward_pe = forward_pe
        config.save()
        self.stdout.write(f'  Macro today: ERP={erp}% ({erp_sig}), composite={composite}')

    def _seed_cron_logs(self):
        CronLog.objects.filter(output__startswith=SEED_MARK).delete()
        now = timezone.now()
        runs = []
        for i, (name, _) in enumerate(CronLog.JOB_CHOICES):
            for run in range(2):
                failed = name == 'update_dividends' and run == 1
                log = CronLog.objects.create(
                    name=name, success=not failed,
                    output=(f'{SEED_MARK} Traceback: ConnectionError: '
                            f'dps.psx.com.pk timed out'
                            if failed else f'{SEED_MARK} OK — 310 rows updated'),
                    duration_seconds=round(4.2 + i * 1.3 + run, 1),
                )
                runs.append((log.pk, now - timedelta(hours=6 * run + i)))
        # auto_now_add ignores passed values on create; stagger via update()
        for pk, ran_at in runs:
            CronLog.objects.filter(pk=pk).update(ran_at=ran_at)
        self.stdout.write(f'  CronLog: {len(runs)} rows (1 failure)')
