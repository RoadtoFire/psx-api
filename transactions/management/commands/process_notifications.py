from decimal import Decimal
from datetime import date
from django.core.management.base import BaseCommand
from stocks.models import Dividend
from transactions.models import Portfolio
from transactions.calculators import get_holdings_on_date, get_purification_rate
from transactions.notifications import send_whatsapp_message


class Command(BaseCommand):
    help = 'Process ex-date notifications for today'

    def handle(self, *args, **options):
        today = date.today()

        todays_dividends = Dividend.objects.filter(
            ex_date=today,
            dividend_type__in=['cash', 'mixed']
        ).select_related('stock')

        if not todays_dividends.exists():
            self.stdout.write('No ex-dates today')
            return

        notifications = 0

        for dividend in todays_dividends:
            portfolios = Portfolio.objects.filter(
                transactions__stock=dividend.stock,
                transactions__date__lte=today
            ).distinct()

            for portfolio in portfolios:
                holdings = get_holdings_on_date(portfolio, today)
                shares = holdings.get(dividend.stock, Decimal('0'))

                if shares <= 0:
                    continue

                user = portfolio.user
                tax_rate = Decimal(str(user.tax_rate))
                gross = shares * dividend.cash_amount
                tax = gross * tax_rate
                net = gross - tax

                purification_rate = get_purification_rate(dividend.stock, today)
                purification_amount = (
                    gross * (Decimal(str(purification_rate)) / 100)
                    if purification_rate else Decimal('0')
                )
                final = net - purification_amount

                self.stdout.write(
                    f'NOTIFICATION → {user.email}: {dividend.stock.symbol} dividend. '
                    f'Gross: Rs.{gross:.2f}, After tax: Rs.{net:.2f}, '
                    f'Pay Rs.{purification_amount:.2f} in charity. Net: Rs.{final:.2f}'
                )

                if user.whatsapp_number:
                    message_body = (
                        f'Amanat: {dividend.stock.symbol} dividend ex-date is today.\n'
                        f'Gross dividend: Rs.{gross:.2f}\n'
                        f'After tax deduction: Rs.{net:.2f}\n'
                        f'Purification amount owed in charity: Rs.{purification_amount:.2f}'
                    )
                    send_whatsapp_message(user.whatsapp_number, message_body)

                notifications += 1

        self.stdout.write(f'Processed {notifications} notifications for {todays_dividends.count()} ex-dates')
