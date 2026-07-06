from rest_framework import serializers
from .models import Stock, DailyPrice, Dividend, PurificationRatio, CronLog, MacroSnapshot, MacroWarning


class DailyPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyPrice
        fields = ['date', 'open', 'close', 'volume']


class DividendSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dividend
        fields = ['ex_date', 'dividend_type', 'cash_amount', 'bonus_ratio']


class PurificationRatioSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurificationRatio
        fields = ['period', 'ratio', 'effective_from', 'effective_to']


class StockListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for stock list — no nested data"""
    latest_price = serializers.SerializerMethodField()
    latest_close = serializers.SerializerMethodField()

    class Meta:
        model = Stock
        fields = ['symbol', 'name', 'sector', 'is_active', 'tv_logo_id', 'latest_price', 'latest_close']

    def get_latest_price(self, obj):
        price = obj.prices.first()
        return float(price.close) if price else None

    def get_latest_close(self, obj):
        price = obj.prices.first()
        return str(price.date) if price else None


class StockDetailSerializer(serializers.ModelSerializer):
    """Full serializer for single stock detail"""
    latest_price_detail = serializers.SerializerMethodField()
    recent_dividends = serializers.SerializerMethodField()
    current_purification = serializers.SerializerMethodField()

    class Meta:
        model = Stock
        fields = [
            'symbol', 'name', 'sector',
            'latest_price_detail', 'recent_dividends', 'current_purification'
        ]

    def get_latest_price_detail(self, obj):
        price = obj.prices.first()
        if not price:
            return None
        return {
            'date': str(price.date),
            'open': float(price.open),
            'close': float(price.close),
            'volume': price.volume,
        }

    def get_recent_dividends(self, obj):
        dividends = obj.dividends.all()[:5]
        return DividendSerializer(dividends, many=True).data

    def get_current_purification(self, obj):
        ratio = obj.purification_ratios.first()
        if not ratio:
            return None
        return PurificationRatioSerializer(ratio).data


class CronLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = CronLog
        fields = ['id', 'name', 'ran_at', 'success', 'output', 'duration_seconds']


class MacroSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = MacroSnapshot
        fields = [
            'date', 'kibor_6m', 'kibor_1y', 'pkr_usd_rate',
            'kse100_forward_pe', 'kse100_earnings_yield',
            'market_erp', 'erp_signal', 'updated_at',
        ]


class MacroWarningSerializer(serializers.ModelSerializer):
    class Meta:
        model = MacroWarning
        fields = [
            'date', 'sbp_fx_reserves_usd_bn', 'monthly_imports_usd_bn',
            'import_cover_months', 'reserves_signal',
            'brent_crude_usd', 'oil_signal',
            'cpi_yoy', 'real_rate', 'real_rate_signal',
            'macro_stress_score', 'composite_signal', 'updated_at',
        ]