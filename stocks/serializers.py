from rest_framework import serializers
from .models import Stock, DailyPrice, Dividend, PurificationRatio


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
    latest_price = serializers.SerializerMethodField()
    recent_dividends = serializers.SerializerMethodField()
    current_purification = serializers.SerializerMethodField()

    class Meta:
        model = Stock
        fields = [
            'symbol', 'name', 'sector',
            'latest_price', 'recent_dividends', 'current_purification'
        ]

    def get_latest_price(self, obj):
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