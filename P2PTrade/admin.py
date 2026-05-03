from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance_myr', 'balance_usd', 'total_balance_usd', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('User', {'fields': ('user',)}),
        ('Balances', {'fields': ('balance_myr', 'balance_usd', 'total_balance_usd')}),
        ('Trading Info', {'fields': ('active_trades', 'monthly_profit_usd')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

