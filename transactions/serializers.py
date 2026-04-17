from rest_framework import serializers
from .models import Portfolio, Transaction
from stocks.models import Stock


class TransactionSerializer(serializers.ModelSerializer):
    stock_symbol = serializers.CharField(write_only=True)
    stock = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Transaction
        fields = [
            'id', 'stock', 'stock_symbol', 'transaction_type',
            'date', 'shares', 'price_per_share', 'total_value'
        ]
        read_only_fields = ['id', 'total_value']

    def validate_stock_symbol(self, value):
        try:
            stock = Stock.objects.get(symbol=value.upper(), is_active=True)
            return stock
        except Stock.DoesNotExist:
            raise serializers.ValidationError(f"{value} is not a valid Shariah compliant stock")

    def create(self, validated_data):
        stock = validated_data.pop('stock_symbol')
        portfolio = validated_data.pop('portfolio')
        return Transaction.objects.create(
            portfolio=portfolio,
            stock=stock,
            **validated_data
        )


class PortfolioSerializer(serializers.ModelSerializer):
    transactions = TransactionSerializer(many=True, read_only=True)

    class Meta:
        model = Portfolio
        fields = ['id', 'name', 'transactions']
        read_only_fields = ['id']