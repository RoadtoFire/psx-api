from django.db import models


class Stock(models.Model):
    symbol = models.CharField(max_length=10, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    sector = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    removed_date = models.DateField(null=True, blank=True)
    tv_logo_id = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        ordering = ['symbol']
        verbose_name_plural = "Stocks"

    def __str__(self):
        return f"{self.symbol} - {self.name}"


class Index(models.Model):
    symbol = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ['symbol']
        verbose_name_plural = "Indices"

    def __str__(self):
        return f"{self.symbol} - {self.name}"


class DailyPrice(models.Model):
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='prices')
    date = models.DateField()
    open = models.DecimalField(max_digits=10, decimal_places=2)
    close = models.DecimalField(max_digits=10, decimal_places=2)
    volume = models.BigIntegerField()

    class Meta:
        ordering = ['-date']
        unique_together = ['stock', 'date']
        verbose_name_plural = "Daily Prices"

    def __str__(self):
        return f"{self.stock.symbol} - {self.date}"


class IndexDailyPrice(models.Model):
    index = models.ForeignKey(Index, on_delete=models.CASCADE, related_name='prices')
    date = models.DateField()
    open = models.DecimalField(max_digits=10, decimal_places=2)
    close = models.DecimalField(max_digits=10, decimal_places=2)
    volume = models.BigIntegerField()

    class Meta:
        ordering = ['-date']
        unique_together = ['index', 'date']
        verbose_name_plural = "Index Daily Prices"

    def __str__(self):
        return f"{self.index.symbol} - {self.date}"
    

class Dividend(models.Model):
    DIVIDEND_TYPES = [
        ('cash', 'Cash Dividend'),
        ('bonus', 'Bonus Shares'),
        ('right', 'Right Shares'),
        ('mixed', 'Cash + Bonus'),
    ]

    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='dividends')
    ex_date = models.DateField()
    dividend_type = models.CharField(max_length=10, choices=DIVIDEND_TYPES)
    cash_amount = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    bonus_ratio = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)
    raw_dividend = models.CharField(max_length=50, blank=True)
    raw_bonus = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-ex_date']
        unique_together = ['stock', 'ex_date']
        verbose_name_plural = "Dividends"

    def __str__(self):
        return f"{self.stock.symbol} - {self.ex_date} - {self.cash_amount}"
    

class PurificationRatio(models.Model):
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='purification_ratios')
    ratio = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)
    # null ratio means Islamic institution - no purification needed
    period = models.CharField(max_length=20)  # e.g., "H1-2025"
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    source_document = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-effective_from']
        unique_together = ['stock', 'effective_from']
        verbose_name_plural = "Purification Ratios"

    def __str__(self):
        ratio_display = f"{self.ratio}%" if self.ratio else "N/A (Islamic)"
        return f"{self.stock.symbol} - {self.period} - {ratio_display}"