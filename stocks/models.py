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


class MacroConfig(models.Model):
    """Single-row table. Access via MacroConfig.get()."""
    kse100_forward_pe = models.FloatField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        'users.User', null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        verbose_name_plural = "Macro Config"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"KSE-100 Forward PE: {self.kse100_forward_pe}"


class MacroSnapshot(models.Model):
    """Daily global macro snapshot — KIBOR, PKR/USD, ERP signal."""
    ERP_CHOICES = [('GREEN', 'Green'), ('YELLOW', 'Yellow'), ('RED', 'Red')]

    date = models.DateField(unique=True, db_index=True)
    kibor_6m = models.FloatField(null=True, blank=True)
    kibor_1y = models.FloatField(null=True, blank=True)
    pkr_usd_rate = models.FloatField(null=True, blank=True)
    kse100_forward_pe = models.FloatField(null=True, blank=True)
    kse100_earnings_yield = models.FloatField(null=True, blank=True)
    market_erp = models.FloatField(null=True, blank=True)
    erp_signal = models.CharField(max_length=10, null=True, blank=True, choices=ERP_CHOICES)
    source = models.CharField(max_length=30, default='sbp_website')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        verbose_name_plural = "Macro Snapshots"

    def __str__(self):
        return f"Macro {self.date} | KIBOR={self.kibor_6m}% | ERP={self.erp_signal}"


class MacroWarning(models.Model):
    """Daily global macro warning signals — reserves, oil, real rate."""
    SIGNAL_CHOICES = [
        ('GREEN', 'Green'), ('YELLOW', 'Yellow'), ('RED', 'Red'), ('UNKNOWN', 'Unknown')
    ]
    COMPOSITE_CHOICES = [
        ('CALM', 'Calm'), ('WATCH', 'Watch'),
        ('STRESSED', 'Stressed'), ('PEAK_STRESS', 'Peak Stress'),
    ]

    date = models.DateField(unique=True, db_index=True)
    sbp_fx_reserves_usd_bn = models.FloatField(null=True, blank=True)
    monthly_imports_usd_bn = models.FloatField(null=True, blank=True)
    import_cover_months = models.FloatField(null=True, blank=True)
    reserves_signal = models.CharField(max_length=10, default='UNKNOWN', choices=SIGNAL_CHOICES)
    brent_crude_usd = models.FloatField(null=True, blank=True)
    oil_signal = models.CharField(max_length=10, default='UNKNOWN', choices=SIGNAL_CHOICES)
    cpi_yoy = models.FloatField(null=True, blank=True)
    real_rate = models.FloatField(null=True, blank=True)
    real_rate_signal = models.CharField(max_length=10, default='UNKNOWN', choices=SIGNAL_CHOICES)
    macro_stress_score = models.IntegerField(default=0)
    composite_signal = models.CharField(max_length=15, default='CALM', choices=COMPOSITE_CHOICES)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        verbose_name_plural = "Macro Warnings"

    def __str__(self):
        return f"Macro Warning {self.date} | {self.composite_signal}"


class CronLog(models.Model):
    JOB_CHOICES = [
        ('update_prices', 'Price Update'),
        ('update_dividends', 'Dividend Update'),
        ('process_notifications', 'Notifications'),
        ('update_macro', 'Macro Update'),
    ]
    name = models.CharField(max_length=30, choices=JOB_CHOICES, db_index=True)
    ran_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=True)
    output = models.TextField(blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ['-ran_at']
        get_latest_by = 'ran_at'
        verbose_name_plural = "Cron Logs"

    def __str__(self):
        status = "OK" if self.success else "FAILED"
        return f"{self.name} [{status}] @ {self.ran_at:%Y-%m-%d %H:%M}"