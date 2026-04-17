from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)
    whatsapp_number = models.CharField(max_length=20, blank=True)

    # Tax filer status — affects dividend tax calculation
    FILER_CHOICES = [
        ('filer', 'Tax Filer'),
        ('non_filer', 'Non-Filer'),
    ]
    filer_status = models.CharField(
        max_length=10,
        choices=FILER_CHOICES,
        default='filer'
    )

    # Make email the login field instead of username
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.email

    @property
    def tax_rate(self):
        """Returns applicable dividend tax rate"""
        return 0.15 if self.filer_status == 'filer' else 0.30