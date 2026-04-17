from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StockViewSet, DailyPriceViewSet

router = DefaultRouter()
router.register(r'stocks', StockViewSet, basename='stock')

urlpatterns = [
    path('', include(router.urls)),
    path(
        'stocks/<str:stock_symbol>/prices/',
        DailyPriceViewSet.as_view({'get': 'list'}),
        name='stock-prices'
    ),
]