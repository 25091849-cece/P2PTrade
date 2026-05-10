from django.contrib import admin
from django.utils.html import format_html
from .models import Deal, Transaction


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_seller_email', 'from_currency', 'to_currency', 'amount', 'rate', 'status_badge', 'expires_at')
    list_filter = ('status', 'trend', 'created_at', 'expires_at')
    search_fields = ('seller__email', 'from_currency__code', 'to_currency__code')
    readonly_fields = ('id', 'created_at', 'expires_at', 'accepted_at')

    fieldsets = (
        ('Seller', {
            'fields': ('seller',)
        }),
        ('Currencies & Amount', {
            'fields': ('from_currency', 'to_currency', 'amount', 'rate')
        }),
        ('Market Info', {
            'fields': ('trend',)
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Dates', {
            'fields': ('created_at', 'expires_at', 'accepted_at'),
            'classes': ('collapse',)
        }),
    )

    def get_seller_email(self, obj):
        return obj.seller.email

    get_seller_email.short_description = 'Seller'

    def status_badge(self, obj):
        colors = {
            'active': 'green',
            'accepted': 'blue',
            'expired': 'red',
            'cancelled': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )

    status_badge.short_description = 'Status'


class TransactionInline(admin.TabularInline):
    """Inline display of transactions for deals."""
    model = Transaction
    extra = 0
    fields = ('id', 'buyer', 'seller', 'type', 'amount', 'status')
    readonly_fields = ('id', 'created_at')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_type_badge', 'get_party', 'amount', 'from_currency', 'to_currency', 'status_badge', 'created_at')
    list_filter = ('type', 'status', 'created_at')
    search_fields = ('buyer__email', 'seller__email', 'user__email', 'payment_reference')
    readonly_fields = ('id', 'timestamp', 'created_at', 'completed_at', 'proof_of_payment_preview')

    fieldsets = (
        ('Parties', {
            'fields': ('buyer', 'seller', 'user')
        }),
        ('Deal Reference', {
            'fields': ('deal',)
        }),
        ('Currencies & Amount', {
            'fields': ('from_currency', 'to_currency', 'amount', 'received_amount', 'rate')
        }),
        ('Status', {
            'fields': ('type', 'status', 'tx_hash')
        }),
        ('Payment', {
            'fields': ('payment_reference', 'proof_of_payment_preview'),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('timestamp', 'created_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )

    def get_type_badge(self, obj):
        colors = {
            'purchase': 'blue',
            'sale': 'green',
            'exchange': 'purple',
            'deposit': 'orange',
            'withdrawal': 'red',
            'offer_created': 'gray'
        }
        color = colors.get(obj.type, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_type_display()
        )

    get_type_badge.short_description = 'Type'

    def get_party(self, obj):
        if obj.buyer and obj.seller:
            return f"{obj.buyer.email} ↔ {obj.seller.email}"
        elif obj.buyer:
            return f"Buy: {obj.buyer.email}"
        elif obj.seller:
            return f"Sell: {obj.seller.email}"
        elif obj.user:
            return obj.user.email
        return "N/A"

    get_party.short_description = 'Party/Parties'

    def status_badge(self, obj):
        colors = {
            'pending': 'blue',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'gray',
            'awaiting_confirmation': 'orange'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )

    status_badge.short_description = 'Status'

    def proof_of_payment_preview(self, obj):
        if obj.proof_of_payment:
            return format_html('<textarea readonly style="width: 100%; height: 100px;">{}</textarea>', obj.proof_of_payment[:200])
        return "No proof uploaded"

    proof_of_payment_preview.short_description = 'Proof of Payment'

