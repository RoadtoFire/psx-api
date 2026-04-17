from celery import shared_task
from datetime import date


@shared_task
def process_ex_date_notifications():
    """
    Every morning check if any stock has ex-date today.
    Calculate dividend for each user holding that stock.
    """
    from stocks.models import Dividend
    from transactions.models import Portfolio
    from transactions.calculators import get_holdings_on_date, get_purification_rate
    from decimal import Decimal

    today = date.today()

    # Find all dividends with ex_date today
    todays_dividends = Dividend.objects.filter(
        ex_date=today,
        dividend_type__in=['cash', 'mixed']
    ).select_related('stock')

    if not todays_dividends:
        return "No ex-dates today"

    notifications = []

    for dividend in todays_dividends:
        # Find all portfolios holding this stock
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
            if purification_rate:
                purification_amount = gross * (Decimal(str(purification_rate)) / 100)
            else:
                purification_amount = Decimal('0')

            final = net - purification_amount

            notification = {
                'user': user.email,
                'stock': dividend.stock.symbol,
                'shares': float(shares),
                'gross': round(float(gross), 2),
                'tax': round(float(tax), 2),
                'purification': round(float(purification_amount), 2),
                'final': round(float(final), 2),
            }
            notifications.append(notification)

            # For now just print — later replace with push/whatsapp notification
            print(f"NOTIFICATION → {user.email}: "
                  f"{dividend.stock.symbol} dividend incoming. "
                  f"Gross: Rs.{gross:.2f}, "
                  f"After tax: Rs.{net:.2f}, "
                  f"Pay Rs.{purification_amount:.2f} in charity. "
                  f"Net to account: Rs.{final:.2f}")

    return f"Processed {len(notifications)} notifications for {todays_dividends.count()} ex-dates"