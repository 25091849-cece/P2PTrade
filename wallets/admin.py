from django.contrib import admin
from .models import Wallet, WalletBalance


class WalletBalanceInline(admin.TabularInline):
    """Inline display of wallet balances."""
    model = WalletBalance
    extra = 0
    fields = ('currency', 'amount', 'last_updated')
    readonly_fields = ('last_updated',)


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('get_user_email', 'balance_total', 'created_at', 'updated_at')
    list_filter = ('created_at',)
    search_fields = ('user__email', 'user__name')
    readonly_fields = ('id', 'created_at', 'updated_at', 'get_total_balance')

    fieldsets = (
        ('User', {
            'fields': ('user', 'id')
        }),
        ('Balance', {
            'fields': ('balance_total', 'get_total_balance')
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    inlines = [WalletBalanceInline]

    def get_user_email(self, obj):
        """Display user email."""
        return obj.user.email

    get_user_email.short_description = 'User Email'

    def has_add_permission(self, request):
        """Wallets are created automatically with users."""
        return False

    def has_delete_permission(self, request):
        """Prevent deletion of wallets."""
        return False


@admin.register(WalletBalance)
class WalletBalanceAdmin(admin.ModelAdmin):
    list_display = ('get_user_email', 'currency', 'amount', 'last_updated')
    list_filter = ('currency', 'last_updated')
    search_fields = ('wallet__user__email', 'currency__code')
    readonly_fields = ('last_updated', 'wallet')

    fieldsets = (
        ('Wallet & Currency', {
            'fields': ('wallet', 'currency')
        }),
        ('Balance', {
            'fields': ('amount',)
        }),
        ('Metadata', {
            'fields': ('last_updated',),
            'classes': ('collapse',)
        }),
    )

    def get_user_email(self, obj):
        """Display user email."""
        return obj.wallet.user.email

    get_user_email.short_description = 'User Email'

