from django.contrib import admin
from .models import Currency, ExchangeRate, ActivityRecord


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'symbol')
    search_fields = ('code', 'name')

    def has_delete_permission(self, request):
        """Prevent deletion of currencies."""
        return False


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ('from_currency', 'to_currency', 'rate', 'change_percent', 'last_updated')
    list_filter = ('from_currency', 'to_currency', 'last_updated')
    search_fields = ('from_currency__code', 'to_currency__code')
    readonly_fields = ('last_updated',)

    fieldsets = (
        ('Currency Pair', {
            'fields': ('from_currency', 'to_currency')
        }),
        ('Rate Information', {
            'fields': ('rate', 'change_percent', 'last_updated')
        }),
    )


@admin.register(ActivityRecord)
class ActivityRecordAdmin(admin.ModelAdmin):
    list_display = ('user', 'activity_type', 'from_currency', 'to_currency', 'amount', 'timestamp')
    list_filter = ('activity_type', 'timestamp')
    search_fields = ('user__email', 'user__name')
    readonly_fields = ('timestamp', 'user')

    def has_add_permission(self, request):
        """Activity records are created automatically."""
        return False

    def has_delete_permission(self, request):
        """Prevent deletion of activity records."""
        return False

