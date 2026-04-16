from django.db import models


class Stock(models.Model):
    symbol = models.CharField(max_length=10, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    sector = models.CharField(max_length=50, blank=True)
    
    # Index membership
    kse_100_member = models.BooleanField(default=False)
    kmi_30_member = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['symbol']

    def __str__(self):
        return f"{self.symbol} - {self.name}"