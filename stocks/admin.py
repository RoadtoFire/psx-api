from django.contrib import admin
from .models import Stock, Index, DailyPrice, IndexDailyPrice


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'name', 'sector']
    search_fields = ['symbol', 'name']


@admin.register(Index)
class IndexAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'name']
    search_fields = ['symbol', 'name']


@admin.register(DailyPrice)
class DailyPriceAdmin(admin.ModelAdmin):
    list_display = ['stock', 'date', 'open', 'close', 'volume']
    list_filter = ['stock']
    date_hierarchy = 'date'


@admin.register(IndexDailyPrice)
class IndexDailyPriceAdmin(admin.ModelAdmin):
    list_display = ['index', 'date', 'open', 'close', 'volume']
    list_filter = ['index']
    date_hierarchy = 'date'