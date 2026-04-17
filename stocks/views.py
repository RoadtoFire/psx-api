from rest_framework import viewsets
from .models import Stock, DailyPrice
from .serializers import StockSerializer, DailyPriceSerializer


class StockViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Stock.objects.all()
    serializer_class = StockSerializer
    lookup_field = 'symbol'

class DailyPriceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DailyPriceSerializer

    def get_queryset(self):
        return DailyPrice.objects.filter(
            stock__symbol = self.kwargs["stock_symbol"]
        )