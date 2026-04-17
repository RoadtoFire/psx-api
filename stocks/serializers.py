from rest_framework import serializers
from .models import Stock, DailyPrice


class DailyPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyPrice
        fields = '__all__'


class StockSerializer(serializers.ModelSerializer):
    prices = DailyPriceSerializer(many=True, read_only=True)
    
    class Meta:
        model = Stock
        fields = '__all__'