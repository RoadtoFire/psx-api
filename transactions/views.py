from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import Portfolio, Transaction
from .serializers import PortfolioSerializer, TransactionSerializer
from .calculators import calculate_dividend_income, calculate_portfolio_value
from rest_framework.views import APIView




class PortfolioView(generics.RetrieveAPIView):
    serializer_class = PortfolioSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        portfolio, _ = Portfolio.objects.get_or_create(
            user=self.request.user,
            defaults={'name': 'My Portfolio'}
        )
        return portfolio


class TransactionCreateView(generics.CreateAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        portfolio, _ = Portfolio.objects.get_or_create(
            user=self.request.user,
            defaults={'name': 'My Portfolio'}
        )
        serializer.save(portfolio=portfolio)


class TransactionDeleteView(generics.DestroyAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(
            portfolio__user=self.request.user
        )
    

class DividendIncomeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        portfolio, _ = Portfolio.objects.get_or_create(
            user=request.user,
            defaults={'name': 'My Portfolio'}
        )

        results = calculate_dividend_income(
            portfolio=portfolio,
            tax_rate=request.user.tax_rate
        )

        # Summary totals
        total_gross = sum(r['gross_dividend'] for r in results)
        total_tax = sum(r['tax_deducted'] for r in results)
        total_purification = sum(r['purification_amount'] for r in results)
        total_net = sum(r['final_amount'] for r in results)

        return Response({
            'summary': {
                'total_gross': round(total_gross, 2),
                'total_tax_deducted': round(total_tax, 2),
                'total_purification': round(total_purification, 2),
                'total_net': round(total_net, 2),
                'filer_status': request.user.filer_status,
                'tax_rate': request.user.tax_rate,
            },
            'dividends': results
        })
    
class PortfolioValueView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        portfolio, _ = Portfolio.objects.get_or_create(
            user=request.user,
            defaults={'name': 'My Portfolio'}
        )
        data = calculate_portfolio_value(portfolio)
        return Response(data)