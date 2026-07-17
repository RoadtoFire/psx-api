import logging
from datetime import date, timedelta
from decimal import Decimal

from rest_framework import viewsets, filters, generics, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Stock, DailyPrice, Index, IndexDailyPrice, CronLog,
    MacroSnapshot, MacroWarning, MacroConfig,
)
from .serializers import (
    StockListSerializer, StockDetailSerializer, DailyPriceSerializer,
    CronLogSerializer, MacroSnapshotSerializer, MacroWarningSerializer,
)

logger = logging.getLogger(__name__)

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


class CronLogListView(generics.ListAPIView):
    serializer_class = CronLogSerializer
    permission_classes = [IsAdminUser]
    pagination_class = None

    def list(self, request, *args, **kwargs):
        # Fetch the latest 10 runs per job so all 4 jobs always appear,
        # regardless of how many times one job dominates the global log.
        job_names = [choice[0] for choice in CronLog.JOB_CHOICES]
        logs = []
        for name in job_names:
            logs.extend(CronLog.objects.filter(name=name).order_by('-ran_at')[:10])
        logs.sort(key=lambda x: x.ran_at, reverse=True)
        serializer = self.get_serializer(logs, many=True)
        return Response(serializer.data)


class MacroView(APIView):
    """
    GET /api/v1/macro/
    Returns the latest MacroSnapshot + MacroWarning, plus the requesting user's
    personal portfolio dividend yield vs KIBOR (personalized dividend gap).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        snapshot = MacroSnapshot.objects.order_by('-date').first()
        warning  = MacroWarning.objects.order_by('-date').first()

        data = {
            "snapshot": MacroSnapshotSerializer(snapshot).data if snapshot else None,
            "warning":  MacroWarningSerializer(warning).data  if warning  else None,
            "personal": self._personal_gap(request.user, snapshot),
        }
        return Response(data)

    def _personal_gap(self, user, snapshot):
        """Compute user's portfolio dividend yield and gap vs KIBOR 6M."""
        try:
            from transactions.models import Portfolio
            from transactions.calculators import get_holdings_on_date

            portfolio = Portfolio.objects.filter(user=user).first()
            if not portfolio:
                return {"portfolio_yield": None, "dividend_gap": None, "holdings_count": 0}

            holdings = get_holdings_on_date(portfolio, date.today())
            if not holdings:
                return {"portfolio_yield": None, "dividend_gap": None, "holdings_count": 0}

            cutoff = date.today() - timedelta(days=365)
            total_weight = Decimal("0")
            weighted_yield = Decimal("0")

            for stock, shares in holdings.items():
                latest_price = DailyPrice.objects.filter(stock=stock).order_by('-date').first()
                if not latest_price or latest_price.close <= 0:
                    continue

                annual_dps = stock.dividends.filter(
                    ex_date__gte=cutoff,
                    dividend_type__in=['cash', 'mixed'],
                    cash_amount__isnull=False,
                    cash_amount__gt=0,
                ).values_list('cash_amount', flat=True)

                total_dps = sum(annual_dps, Decimal("0"))
                if total_dps <= 0:
                    continue

                ticker_yield = (total_dps / latest_price.close * 100).quantize(Decimal("0.01"))
                total_weight += shares
                weighted_yield += shares * ticker_yield

            if total_weight <= 0:
                return {"portfolio_yield": None, "dividend_gap": None, "holdings_count": len(holdings)}

            portfolio_yield = float((weighted_yield / total_weight).quantize(Decimal("0.01")))
            kibor = snapshot.kibor_6m if snapshot else None
            gap = round(portfolio_yield - kibor, 2) if kibor is not None else None

            return {
                "portfolio_yield": portfolio_yield,
                "dividend_gap": gap,
                "holdings_count": len(holdings),
            }

        except Exception:
            logger.exception("Personal dividend gap calculation failed for user %s", user.pk)
            return {"portfolio_yield": None, "dividend_gap": None, "holdings_count": 0}


class SetForwardPEView(APIView):
    """
    POST /api/v1/admin/macro/set-pe/
    Body: { "forward_pe": 6.8 }
    Updates MacroConfig and immediately patches today's MacroSnapshot.
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        pe_val = request.data.get("forward_pe")
        try:
            pe = float(pe_val)
            if pe <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return Response({"error": "forward_pe must be a positive number."}, status=status.HTTP_400_BAD_REQUEST)

        config = MacroConfig.get()
        config.kse100_forward_pe = pe
        config.updated_by = request.user
        config.save()

        earnings_yield = round(100.0 / pe, 4)

        snapshot, _ = MacroSnapshot.objects.update_or_create(
            date=date.today(),
            defaults={
                "kse100_forward_pe": pe,
                "kse100_earnings_yield": earnings_yield,
            }
        )
        # Recompute ERP signal if KIBOR is available
        if snapshot.kibor_6m is not None:
            market_erp = round(earnings_yield - snapshot.kibor_6m, 4)
            from stocks.management.commands.update_macro import erp_signal
            sig = erp_signal(market_erp, None)
            snapshot.market_erp = market_erp
            snapshot.erp_signal = sig
            snapshot.save(update_fields=["market_erp", "erp_signal", "kse100_forward_pe", "kse100_earnings_yield"])

        return Response(MacroSnapshotSerializer(snapshot).data)