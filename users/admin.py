from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['email', 'username', 'filer_status', 'is_active']
    list_filter = ['filer_status', 'is_active']
    search_fields = ['email', 'username']

    fieldsets = UserAdmin.fieldsets + (
        ('PSX Investor Info', {
            'fields': ('whatsapp_number', 'filer_status')
        }),
    )