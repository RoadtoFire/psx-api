from django.contrib import admin
from .models import Portfolio, Transaction


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'created_at']
    search_fields = ['user__email']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['portfolio', 'stock', 'transaction_type', 'date', 'shares', 'price_per_share']
    list_filter = ['transaction_type', 'date']
    search_fields = ['portfolio__user__email', 'stock__symbol']
    date_hierarchy = 'date'