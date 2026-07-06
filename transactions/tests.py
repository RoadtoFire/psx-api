from decimal import Decimal

from django.test import TestCase

from stocks.models import Stock, DailyPrice, Dividend, PurificationRatio
from transactions.models import Portfolio, Transaction
from transactions.calculators import (
    get_holdings_on_date,
    get_purification_rate,
    calculate_dividend_income,
    calculate_portfolio_value,
)
from users.models import User


class HoldingsCalculationTests(TestCase):
    """Tests for get_holdings_on_date: replaying buy/sell transactions."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='holder', email='holder@example.com', password='pw12345',
        )
        self.portfolio = Portfolio.objects.create(user=self.user, name='Main')
        self.stock_a = Stock.objects.create(symbol='AAA', name='Alpha Co')
        self.stock_b = Stock.objects.create(symbol='BBB', name='Beta Co')

    def _buy(self, stock, date, shares, price):
        return Transaction.objects.create(
            portfolio=self.portfolio, stock=stock, transaction_type='buy',
            date=date, shares=Decimal(shares), price_per_share=Decimal(price),
        )

    def _sell(self, stock, date, shares, price):
        return Transaction.objects.create(
            portfolio=self.portfolio, stock=stock, transaction_type='sell',
            date=date, shares=Decimal(shares), price_per_share=Decimal(price),
        )

    def test_buy_then_partial_sell_leaves_correct_remainder(self):
        # Buy 100, sell 40 -> 60 remaining.
        self._buy(self.stock_a, '2025-01-01', '100', '10.00')
        self._sell(self.stock_a, '2025-02-01', '40', '12.00')

        holdings = get_holdings_on_date(self.portfolio, '2025-03-01')

        self.assertEqual(holdings, {self.stock_a: Decimal('60')})

    def test_sell_down_to_exactly_zero_excludes_stock(self):
        # Buy 50, sell 50 -> 0 remaining -> stock must not appear at all.
        self._buy(self.stock_a, '2025-01-01', '50', '10.00')
        self._sell(self.stock_a, '2025-02-01', '50', '11.00')

        holdings = get_holdings_on_date(self.portfolio, '2025-03-01')

        self.assertEqual(holdings, {})
        self.assertNotIn(self.stock_a, holdings)

    def test_query_before_any_transactions_returns_empty_dict(self):
        self._buy(self.stock_a, '2025-06-01', '100', '10.00')

        holdings = get_holdings_on_date(self.portfolio, '2025-01-01')

        self.assertEqual(holdings, {})

    def test_multiple_stocks_held_simultaneously_independent_quantities(self):
        self._buy(self.stock_a, '2025-01-01', '100', '10.00')
        self._buy(self.stock_b, '2025-01-15', '30', '5.00')
        self._sell(self.stock_a, '2025-02-01', '25', '11.00')

        holdings = get_holdings_on_date(self.portfolio, '2025-03-01')

        self.assertEqual(holdings, {
            self.stock_a: Decimal('75'),
            self.stock_b: Decimal('30'),
        })


class PurificationRateLookupTests(TestCase):
    """Tests for get_purification_rate: period-boundary lookup logic."""

    def setUp(self):
        self.stock = Stock.objects.create(symbol='CCC', name='Gamma Co')

    def test_two_periods_returns_correct_period_for_each_date(self):
        # Older period: effective 2025-01-03, ratio 4.50%
        # Newer period: effective 2025-06-10, ratio 2.10%
        PurificationRatio.objects.create(
            stock=self.stock, ratio=Decimal('4.5000'), period='H1-2024',
            effective_from='2025-01-03', effective_to='2025-06-09',
        )
        PurificationRatio.objects.create(
            stock=self.stock, ratio=Decimal('2.1000'), period='H2-2024',
            effective_from='2025-06-10', effective_to=None,
        )

        # A date within the OLDER period must return the older ratio,
        # not just "whatever is latest overall".
        rate_in_old_period = get_purification_rate(self.stock, '2025-03-15')
        self.assertEqual(rate_in_old_period, Decimal('4.5000'))

        # A date within the newer period must return the newer ratio.
        rate_in_new_period = get_purification_rate(self.stock, '2025-09-01')
        self.assertEqual(rate_in_new_period, Decimal('2.1000'))

    def test_islamic_institution_with_null_ratio_returns_none(self):
        PurificationRatio.objects.create(
            stock=self.stock, ratio=None, period='H1-2024',
            effective_from='2025-01-03', effective_to=None,
        )

        rate = get_purification_rate(self.stock, '2025-05-01')

        self.assertIsNone(rate)

    def test_stock_with_no_purification_record_returns_none_without_crashing(self):
        rate = get_purification_rate(self.stock, '2025-05-01')

        self.assertIsNone(rate)


class DividendIncomeCalculationTests(TestCase):
    """Tests for calculate_dividend_income: cash, bonus, mixed dividends."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='investor', email='investor@example.com', password='pw12345',
        )
        self.portfolio = Portfolio.objects.create(user=self.user, name='Main')
        self.stock = Stock.objects.create(symbol='DDD', name='Delta Co')

        # Holder buys 200 shares well before any dividend, and never sells
        # (unless a specific test overrides this).
        Transaction.objects.create(
            portfolio=self.portfolio, stock=self.stock, transaction_type='buy',
            date='2025-01-01', shares=Decimal('200'), price_per_share=Decimal('50.00'),
        )

    def test_pure_cash_dividend_with_purification_ratio(self):
        PurificationRatio.objects.create(
            stock=self.stock, ratio=Decimal('5.0000'), period='H1-2024',
            effective_from='2025-01-01', effective_to=None,
        )
        Dividend.objects.create(
            stock=self.stock, ex_date='2025-03-01', dividend_type='cash',
            cash_amount=Decimal('2.50'), bonus_ratio=None,
        )

        results = calculate_dividend_income(self.portfolio, tax_rate=0.15)

        self.assertEqual(len(results), 1)
        r = results[0]

        # By hand: 200 shares * 2.50 = 500 gross
        # tax = 500 * 0.15 = 75
        # net = 500 - 75 = 425
        # purification = 500 * (5.0 / 100) = 25
        # final = 425 - 25 = 400
        self.assertEqual(r['gross_dividend'], 500.0)
        self.assertEqual(r['tax_deducted'], 75.0)
        self.assertEqual(r['net_dividend'], 425.0)
        self.assertEqual(r['purification_amount'], 25.0)
        self.assertEqual(r['final_amount'], 400.0)

    def test_pure_cash_dividend_islamic_institution_zero_purification(self):
        PurificationRatio.objects.create(
            stock=self.stock, ratio=None, period='H1-2024',
            effective_from='2025-01-01', effective_to=None,
        )
        Dividend.objects.create(
            stock=self.stock, ex_date='2025-03-01', dividend_type='cash',
            cash_amount=Decimal('2.50'), bonus_ratio=None,
        )

        results = calculate_dividend_income(self.portfolio, tax_rate=0.15)

        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r['purification_amount'], 0.0)
        # final_amount should equal net_dividend exactly when purification is 0.
        self.assertEqual(r['final_amount'], r['net_dividend'])

    def test_dividend_before_purchase_is_excluded(self):
        Dividend.objects.create(
            stock=self.stock, ex_date='2024-06-01', dividend_type='cash',
            cash_amount=Decimal('1.00'), bonus_ratio=None,
        )

        results = calculate_dividend_income(self.portfolio, tax_rate=0.15)

        self.assertEqual(results, [])

    def test_dividend_after_full_sale_is_excluded(self):
        Transaction.objects.create(
            portfolio=self.portfolio, stock=self.stock, transaction_type='sell',
            date='2025-02-01', shares=Decimal('200'), price_per_share=Decimal('55.00'),
        )
        Dividend.objects.create(
            stock=self.stock, ex_date='2025-03-01', dividend_type='cash',
            cash_amount=Decimal('1.00'), bonus_ratio=None,
        )

        results = calculate_dividend_income(self.portfolio, tax_rate=0.15)

        self.assertEqual(results, [])

    def test_pure_bonus_dividend_with_price_and_purification(self):
        PurificationRatio.objects.create(
            stock=self.stock, ratio=Decimal('10.0000'), period='H1-2024',
            effective_from='2025-01-01', effective_to=None,
        )
        DailyPrice.objects.create(
            stock=self.stock, date='2025-02-25', open=Decimal('60.00'),
            close=Decimal('60.00'), volume=1000,
        )
        Dividend.objects.create(
            stock=self.stock, ex_date='2025-03-01', dividend_type='bonus',
            cash_amount=None, bonus_ratio=Decimal('0.1000'),
        )

        results = calculate_dividend_income(self.portfolio, tax_rate=0.15)

        self.assertEqual(len(results), 1)
        r = results[0]

        # cash_amount is None -> gross/tax/net are all 0, no crash.
        self.assertEqual(r['gross_dividend'], 0.0)
        self.assertEqual(r['tax_deducted'], 0.0)
        self.assertEqual(r['net_dividend'], 0.0)

        # By hand: bonus_shares_received = 200 * 0.10 = 20 shares
        # bonus_value = 20 * 60.00 = 1200
        # bonus_purification = 1200 * (10.0 / 100) = 120
        # purification_amount = cash_purification(0) + bonus_purification(120) = 120
        self.assertEqual(r['bonus_shares_received'], 20.0)
        self.assertEqual(r['bonus_value'], 1200.0)
        self.assertEqual(r['purification_amount'], 120.0)

        # final_amount = net(0) - purification(120) = -120
        self.assertEqual(r['final_amount'], -120.0)

    def test_mixed_dividend_sums_cash_and_bonus_purification(self):
        PurificationRatio.objects.create(
            stock=self.stock, ratio=Decimal('4.0000'), period='H1-2024',
            effective_from='2025-01-01', effective_to=None,
        )
        DailyPrice.objects.create(
            stock=self.stock, date='2025-02-20', open=Decimal('40.00'),
            close=Decimal('40.00'), volume=1000,
        )
        Dividend.objects.create(
            stock=self.stock, ex_date='2025-03-01', dividend_type='mixed',
            cash_amount=Decimal('3.00'), bonus_ratio=Decimal('0.0500'),
        )

        results = calculate_dividend_income(self.portfolio, tax_rate=0.15)

        self.assertEqual(len(results), 1)
        r = results[0]

        # Cash side: gross = 200 * 3.00 = 600
        # tax = 600 * 0.15 = 90; net = 510
        # cash_purification = 600 * (4.0/100) = 24
        self.assertEqual(r['gross_dividend'], 600.0)
        self.assertEqual(r['tax_deducted'], 90.0)
        self.assertEqual(r['net_dividend'], 510.0)

        # Bonus side: bonus_shares = 200 * 0.05 = 10
        # bonus_value = 10 * 40.00 = 400
        # bonus_purification = 400 * (4.0/100) = 16
        self.assertEqual(r['bonus_shares_received'], 10.0)
        self.assertEqual(r['bonus_value'], 400.0)

        # Combined purification_amount = cash_purification(24) + bonus_purification(16) = 40
        self.assertEqual(r['purification_amount'], 40.0)

        # final = net(510) - purification(40) = 470
        self.assertEqual(r['final_amount'], 470.0)

    def test_bonus_dividend_with_no_price_history_falls_back_to_zero(self):
        # No DailyPrice exists at all for this stock, so price_record lookup
        # returns None. Per the current implementation, bonus_value/purification
        # then fall back to their Decimal('0') initial values rather than crashing.
        PurificationRatio.objects.create(
            stock=self.stock, ratio=Decimal('10.0000'), period='H1-2024',
            effective_from='2025-01-01', effective_to=None,
        )
        Dividend.objects.create(
            stock=self.stock, ex_date='2025-03-01', dividend_type='bonus',
            cash_amount=None, bonus_ratio=Decimal('0.1000'),
        )

        results = calculate_dividend_income(self.portfolio, tax_rate=0.15)

        self.assertEqual(len(results), 1)
        r = results[0]

        # bonus_shares_received is still computed (no price needed for that part).
        self.assertEqual(r['bonus_shares_received'], 20.0)
        # But value/purification fall back to 0 because there is no price record.
        self.assertEqual(r['bonus_value'], 0.0)
        self.assertEqual(r['purification_amount'], 0.0)
        self.assertEqual(r['final_amount'], 0.0)

    def test_different_tax_rates_produce_different_tax_and_net(self):
        Dividend.objects.create(
            stock=self.stock, ex_date='2025-03-01', dividend_type='cash',
            cash_amount=Decimal('2.00'), bonus_ratio=None,
        )

        results_filer = calculate_dividend_income(self.portfolio, tax_rate=0.15)
        results_non_filer = calculate_dividend_income(self.portfolio, tax_rate=0.30)

        # gross = 200 * 2.00 = 400 in both cases.
        gross = 400.0
        self.assertEqual(results_filer[0]['gross_dividend'], gross)
        self.assertEqual(results_non_filer[0]['gross_dividend'], gross)

        # Filer (0.15): tax = 60, net = 340
        self.assertEqual(results_filer[0]['tax_deducted'], 60.0)
        self.assertEqual(results_filer[0]['net_dividend'], 340.0)

        # Non-filer (0.30): tax = 120, net = 280
        self.assertEqual(results_non_filer[0]['tax_deducted'], 120.0)
        self.assertEqual(results_non_filer[0]['net_dividend'], 280.0)

        self.assertNotEqual(
            results_filer[0]['tax_deducted'], results_non_filer[0]['tax_deducted']
        )
        self.assertNotEqual(
            results_filer[0]['net_dividend'], results_non_filer[0]['net_dividend']
        )


class PortfolioValueCalculationTests(TestCase):
    """Tests for calculate_portfolio_value: current value, cost basis, P&L."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='valuer', email='valuer@example.com', password='pw12345',
        )
        self.portfolio = Portfolio.objects.create(user=self.user, name='Main')
        self.stock = Stock.objects.create(symbol='EEE', name='Epsilon Co')

    def test_single_buy_with_known_price_computes_value_cost_pnl(self):
        Transaction.objects.create(
            portfolio=self.portfolio, stock=self.stock, transaction_type='buy',
            date='2025-01-01', shares=Decimal('100'), price_per_share=Decimal('20.00'),
        )
        DailyPrice.objects.create(
            stock=self.stock, date='2025-06-01', open=Decimal('24.00'),
            close=Decimal('25.00'), volume=5000,
        )

        result = calculate_portfolio_value(self.portfolio)

        self.assertEqual(len(result['holdings']), 1)
        h = result['holdings'][0]

        # By hand: current_value = 100 * 25.00 = 2500
        # cost_basis = 100 * 20.00 = 2000
        # pnl = 2500 - 2000 = 500
        # pnl_pct = 500/2000*100 = 25.0
        self.assertEqual(h['shares'], 100.0)
        self.assertEqual(h['avg_buy_price'], 20.0)
        self.assertEqual(h['current_price'], 25.0)
        self.assertEqual(h['current_value'], 2500.0)
        self.assertEqual(h['cost_basis'], 2000.0)
        self.assertEqual(h['pnl'], 500.0)
        self.assertEqual(h['pnl_pct'], 25.0)

        self.assertEqual(result['summary']['total_current_value'], 2500.0)
        self.assertEqual(result['summary']['total_cost_basis'], 2000.0)
        self.assertEqual(result['summary']['total_pnl'], 500.0)
        self.assertEqual(result['summary']['total_pnl_pct'], 25.0)

    def test_partial_sell_uses_average_cost_of_remaining_shares_only(self):
        # Two buy lots at different prices, then a partial sell.
        # Buy 100 @ 10.00, buy 100 @ 20.00 -> avg cost across ALL buys = 15.00.
        # Sell 100 of the 200 -> 100 remain.
        # NOTE: avg_buy_price in the current implementation is computed from
        # ALL buy transactions (not reduced for the sell), so avg_buy_price
        # stays 15.00, and cost_basis = remaining_shares(100) * 15.00 = 1500,
        # reflecting only the REMAINING share count times that average cost.
        Transaction.objects.create(
            portfolio=self.portfolio, stock=self.stock, transaction_type='buy',
            date='2025-01-01', shares=Decimal('100'), price_per_share=Decimal('10.00'),
        )
        Transaction.objects.create(
            portfolio=self.portfolio, stock=self.stock, transaction_type='buy',
            date='2025-02-01', shares=Decimal('100'), price_per_share=Decimal('20.00'),
        )
        Transaction.objects.create(
            portfolio=self.portfolio, stock=self.stock, transaction_type='sell',
            date='2025-03-01', shares=Decimal('100'), price_per_share=Decimal('22.00'),
        )
        DailyPrice.objects.create(
            stock=self.stock, date='2025-06-01', open=Decimal('17.00'),
            close=Decimal('18.00'), volume=5000,
        )

        result = calculate_portfolio_value(self.portfolio)

        self.assertEqual(len(result['holdings']), 1)
        h = result['holdings'][0]

        # remaining shares = 200 - 100 = 100
        self.assertEqual(h['shares'], 100.0)
        # avg_buy_price computed across all buy txns: (100*10 + 100*20)/200 = 15.00
        self.assertEqual(h['avg_buy_price'], 15.0)
        # cost_basis = remaining shares(100) * avg_buy_price(15.00) = 1500
        self.assertEqual(h['cost_basis'], 1500.0)
        # current_value = 100 * 18.00 = 1800
        self.assertEqual(h['current_value'], 1800.0)
        # pnl = 1800 - 1500 = 300; pnl_pct = 300/1500*100 = 20.0
        self.assertEqual(h['pnl'], 300.0)
        self.assertEqual(h['pnl_pct'], 20.0)

    def test_stock_with_no_daily_price_is_excluded(self):
        Transaction.objects.create(
            portfolio=self.portfolio, stock=self.stock, transaction_type='buy',
            date='2025-01-01', shares=Decimal('50'), price_per_share=Decimal('30.00'),
        )
        # No DailyPrice created at all for this stock.

        result = calculate_portfolio_value(self.portfolio)

        self.assertEqual(result['holdings'], [])
        self.assertEqual(result['summary']['total_current_value'], 0.0)
        self.assertEqual(result['summary']['total_cost_basis'], 0.0)
        self.assertEqual(result['summary']['total_pnl'], 0.0)
        self.assertEqual(result['summary']['total_pnl_pct'], 0.0)
