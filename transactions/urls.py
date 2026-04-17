from django.urls import path
from .views import PortfolioView, TransactionCreateView, TransactionDeleteView, DividendIncomeView

urlpatterns = [
    path('portfolio/', PortfolioView.as_view(), name='portfolio'),
    path('portfolio/transactions/', TransactionCreateView.as_view(), name='transaction-create'),
    path('portfolio/transactions/<int:pk>/', TransactionDeleteView.as_view(), name='transaction-delete'),
    path('portfolio/dividends/', DividendIncomeView.as_view(), name='dividend-income'),
]