from django.contrib import admin
from .models import Stock


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'name', 'sector', 'kse_100_member', 'kmi_30_member']
    list_filter = ['sector', 'kse_100_member', 'kmi_30_member']
    search_fields = ['symbol', 'name']