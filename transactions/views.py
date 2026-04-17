from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import Portfolio, Transaction
from .serializers import PortfolioSerializer, TransactionSerializer


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