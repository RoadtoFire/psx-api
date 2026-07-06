from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StockViewSet, DailyPriceViewSet, CronLogListView, MacroView, SetForwardPEView

router = DefaultRouter()
router.register(r'stocks', StockViewSet, basename='stock')

urlpatterns = [
    path('', include(router.urls)),
    path(
        'stocks/<str:stock_symbol>/prices/',
        DailyPriceViewSet.as_view({'get': 'list'}),
        name='stock-prices'
    ),
    path('admin/cron-logs/', CronLogListView.as_view(), name='cron-logs'),
    path('macro/', MacroView.as_view(), name='macro'),
    path('admin/macro/set-pe/', SetForwardPEView.as_view(), name='macro-set-pe'),
]