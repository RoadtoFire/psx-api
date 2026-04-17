from django.db import models
from django.conf import settings
from stocks.models import Stock


class Portfolio(models.Model):
    """A user can have one portfolio (expandable to multiple later)"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='portfolio'
    )
    name = models.CharField(max_length=100, default='My Portfolio')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.name}"


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('buy', 'Buy'),
        ('sell', 'Sell'),
    ]

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    stock = models.ForeignKey(
        Stock,
        on_delete=models.PROTECT,
        related_name='transactions'
    )
    transaction_type = models.CharField(max_length=4, choices=TRANSACTION_TYPES)
    date = models.DateField()
    shares = models.DecimalField(max_digits=12, decimal_places=4)
    price_per_share = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ['-date']
        verbose_name_plural = 'Transactions'

    def __str__(self):
        return f"{self.portfolio.user.email} - {self.transaction_type.upper()} {self.shares} {self.stock.symbol} @ {self.price_per_share}"

    @property
    def total_value(self):
        return self.shares * self.price_per_share