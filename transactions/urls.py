from django.urls import path
from .views import PortfolioView, TransactionCreateView, TransactionDeleteView, DividendIncomeView, PortfolioValueView, MarkPurifiedView, PurificationHistoryView

urlpatterns = [
    path('portfolio/', PortfolioView.as_view(), name='portfolio'),
    path('portfolio/transactions/', TransactionCreateView.as_view(), name='transaction-create'),
    path('portfolio/transactions/<int:pk>/', TransactionDeleteView.as_view(), name='transaction-delete'),
    path('portfolio/dividends/', DividendIncomeView.as_view(), name='dividend-income'),
    path('portfolio/value/', PortfolioValueView.as_view(), name='portfolio-value'),
    path('portfolio/purification/mark/', MarkPurifiedView.as_view(), name='mark-purified'),
    path('portfolio/purification/history/', PurificationHistoryView.as_view(), name='purification-history'),
]