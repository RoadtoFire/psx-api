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


def calculate_portfolio_value(portfolio):
    """
    Calculate current portfolio value and returns.
    Returns holdings with current value, cost basis, and P&L.
    """
    from stocks.models import DailyPrice
    from datetime import date

    today = date.today()
    holdings = get_holdings_on_date(portfolio, today)

    results = []
    total_current_value = Decimal('0')
    total_cost_basis = Decimal('0')

    for stock, shares in holdings.items():
        # Get latest price
        latest_price = DailyPrice.objects.filter(
            stock=stock
        ).order_by('-date').first()

        if not latest_price:
            continue

        # Get average buy price for this stock
        buy_transactions = portfolio.transactions.filter(
            stock=stock,
            transaction_type='buy'
        )
        total_spent = sum(t.shares * t.price_per_share for t in buy_transactions)
        total_bought = sum(t.shares for t in buy_transactions)
        avg_buy_price = total_spent / total_bought if total_bought else Decimal('0')

        current_value = shares * latest_price.close
        cost_basis = shares * avg_buy_price
        pnl = current_value - cost_basis
        pnl_pct = (pnl / cost_basis * 100) if cost_basis else Decimal('0')

        total_current_value += current_value
        total_cost_basis += cost_basis

        results.append({
            'stock': stock.symbol,
            'stock_name': stock.name,
            'shares': float(shares),
            'avg_buy_price': round(float(avg_buy_price), 2),
            'current_price': float(latest_price.close),
            'price_date': str(latest_price.date),
            'current_value': round(float(current_value), 2),
            'cost_basis': round(float(cost_basis), 2),
            'pnl': round(float(pnl), 2),
            'pnl_pct': round(float(pnl_pct), 2),
        })

    total_pnl = total_current_value - total_cost_basis
    total_pnl_pct = (total_pnl / total_cost_basis * 100) if total_cost_basis else Decimal('0')

    return {
        'summary': {
            'total_current_value': round(float(total_current_value), 2),
            'total_cost_basis': round(float(total_cost_basis), 2),
            'total_pnl': round(float(total_pnl), 2),
            'total_pnl_pct': round(float(total_pnl_pct), 2),
        },
        'holdings': results
    }