from django.contrib import admin
from .models import Stock, Index, DailyPrice, IndexDailyPrice, Dividend, PurificationRatio


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


@admin.register(Dividend)
class DividendAdmin(admin.ModelAdmin):
    list_display = ['stock', 'ex_date', 'dividend_type', 'cash_amount', 'bonus_ratio']
    list_filter = ['dividend_type', 'stock']
    date_hierarchy = 'ex_date'
    search_fields = ['stock__symbol']


@admin.register(PurificationRatio)
class PurificationRatioAdmin(admin.ModelAdmin):
    list_display = ['stock', 'period', 'ratio', 'effective_from', 'effective_to']
    search_fields = ['stock__symbol']
    list_filter = ['period']