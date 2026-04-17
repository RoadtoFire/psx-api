from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from .models import Stock, DailyPrice, Index, IndexDailyPrice
from .serializers import (
    StockListSerializer, StockDetailSerializer, DailyPriceSerializer
)

class StockViewSet(viewsets.ReadOnlyModelViewSet):
    lookup_field = 'symbol'
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['symbol', 'name', 'sector']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return StockDetailSerializer
        return StockListSerializer

    def get_queryset(self):
        queryset = Stock.objects.filter(is_active=True)
        sector = self.request.query_params.get('sector', '')
        if sector:
            queryset = queryset.filter(sector=sector)
        return queryset

    @action(detail=True, methods=['get'])
    def prices(self, request, symbol=None):
        stock = self.get_object()
        queryset = stock.prices.all()
        from_date = request.query_params.get('from')
        to_date = request.query_params.get('to')
        if from_date:
            queryset = queryset.filter(date__gte=from_date)
        if to_date:
            queryset = queryset.filter(date__lte=to_date)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = DailyPriceSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = DailyPriceSerializer(queryset, many=True)
        return Response(serializer.data)


class DailyPriceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DailyPriceSerializer

    def get_queryset(self):
        return DailyPrice.objects.filter(
            stock__symbol=self.kwargs["stock_symbol"]
        )