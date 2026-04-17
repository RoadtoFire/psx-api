from decimal import Decimal
from stocks.models import Dividend, PurificationRatio


def get_holdings_on_date(portfolio, date):
    """
    Calculate how many shares of each stock a user held on a specific date.
    Returns dict: {stock: shares}
    """
    holdings = {}
    transactions = portfolio.transactions.filter(date__lte=date)

    for t in transactions:
        if t.stock not in holdings:
            holdings[t.stock] = Decimal('0')
        if t.transaction_type == 'buy':
            holdings[t.stock] += t.shares
        elif t.transaction_type == 'sell':
            holdings[t.stock] -= t.shares

    # Remove stocks with zero or negative holdings
    return {stock: shares for stock, shares in holdings.items() if shares > 0}


def get_purification_rate(stock, date):
    """Get the applicable purification rate for a stock on a given date"""
    ratio = PurificationRatio.objects.filter(
        stock=stock,
        effective_from__lte=date
    ).order_by('-effective_from').first()

    if not ratio:
        return None

    return ratio.ratio  # None means Islamic institution - no purification needed


def calculate_dividend_income(portfolio, tax_rate):
    """
    Calculate complete dividend income for a portfolio.
    Returns list of dividend events with tax and purification calculations.
    """
    results = []

    # Get all dividends for stocks ever held
    held_stocks = portfolio.transactions.values_list('stock', flat=True).distinct()
    dividends = Dividend.objects.filter(
        stock__in=held_stocks,
        dividend_type__in=['cash', 'mixed']
    ).order_by('-ex_date')

    for dividend in dividends:
        # Get holdings on the ex_date
        holdings = get_holdings_on_date(portfolio, dividend.ex_date)
        shares_held = holdings.get(dividend.stock, Decimal('0'))

        if shares_held <= 0:
            continue

        # Calculate amounts
        gross = shares_held * dividend.cash_amount
        tax = gross * Decimal(str(tax_rate))
        net = gross - tax

        # Purification
        purification_rate = get_purification_rate(dividend.stock, dividend.ex_date)
        if purification_rate:
            purification_amount = gross * (Decimal(str(purification_rate)) / 100)
        else:
            purification_amount = Decimal('0')

        results.append({
            'stock': dividend.stock.symbol,
            'stock_name': dividend.stock.name,
            'ex_date': str(dividend.ex_date),
            'shares_held': float(shares_held),
            'cash_amount_per_share': float(dividend.cash_amount),
            'gross_dividend': round(float(gross), 2),
            'tax_deducted': round(float(tax), 2),
            'net_dividend': round(float(net), 2),
            'purification_rate': float(purification_rate) if purification_rate else None,
            'purification_amount': round(float(purification_amount), 2),
            'final_amount': round(float(net - purification_amount), 2),
        })

    return results