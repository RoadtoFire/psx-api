from django.db import models


class Stock(models.Model):
    symbol = models.CharField(max_length=10, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    sector = models.CharField(max_length=50, blank=True)

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