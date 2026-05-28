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
    list_display = ('id', 'get_type_badge', 'get_buyer', 'get_seller', 'get_user', 'get_buyer_pays', 'get_buyer_gets', 'status_badge', 'created_at')
    list_filter = ('type', 'status', 'created_at')
    search_fields = ('buyer__email', 'seller__email', 'user__email', 'payment_reference')
    readonly_fields = ('id', 'received_amount', 'timestamp', 'created_at', 'completed_at', 'proof_of_payment_preview')

    fieldsets = (
        ('Parties', {
            'fields': ('buyer', 'seller', 'user')
        }),
        ('Currencies & Amount', {
            'fields': ('from_currency', 'to_currency', 'amount', 'received_amount', 'rate')
        }),
        ('Status', {
            'fields': ('type', 'status')
        }),
        ('Dates', {
            'fields': ('timestamp', 'created_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )

    def get_type_badge(self, obj):
        colors = {
            'deposit': 'blue',
            'withdrawal': 'purple',
            'exchange': 'green',
        }
        color = colors.get(obj.type, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_type_display()
        )

    get_type_badge.short_description = 'Type'

    def get_buyer(self, obj):
        return obj.buyer.email if obj.buyer else '—'

    get_buyer.short_description = 'Buyer'

    def get_seller(self, obj):
        return obj.seller.email if obj.seller else '—'

    get_seller.short_description = 'Seller'

    def get_user(self, obj):
        return obj.user.email if obj.user else '—'

    get_user.short_description = 'User'

    def get_buyer_pays(self, obj):
        return f"{obj.amount} {obj.from_currency.code}"

    get_buyer_pays.short_description = 'Buyer Pays'

    def get_buyer_gets(self, obj):
        if obj.received_amount:
            return f"{obj.received_amount} {obj.to_currency.code}"
        return f"? {obj.to_currency.code}"

    get_buyer_gets.short_description = 'Buyer Gets'

    def status_badge(self, obj):
        colors = {
            'completed': 'green',
            'pending': 'orange',
            'failed': 'red',
            'dispute_raised': 'purple',
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

