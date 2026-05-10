from django.contrib import admin
from django.utils.html import format_html
from .models import Dispute, DisputeResolution, DisputeMessage, DisputeActivityLog


class DisputeMessageInline(admin.TabularInline):
    """Inline display of dispute messages."""
    model = DisputeMessage
    extra = 0
    fields = ('sender', 'message', 'is_admin_message', 'created_at')
    readonly_fields = ('created_at', 'sender')


class DisputeActivityLogInline(admin.TabularInline):
    """Inline display of dispute activity logs."""
    model = DisputeActivityLog
    extra = 0
    fields = ('actor', 'action', 'timestamp')
    readonly_fields = ('timestamp', 'actor')


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_buyer_email', 'get_seller_email', 'status_badge', 'created_at', 'resolved_at')
    list_filter = ('status', 'created_at', 'resolved_at')
    search_fields = ('buyer__email', 'seller__email', 'raised_by__email', 'reason')
    readonly_fields = ('id', 'created_at', 'resolved_at')

    fieldsets = (
        ('Transaction & Parties', {
            'fields': ('transaction', 'buyer', 'seller', 'raised_by')
        }),
        ('Currencies & Amounts', {
            'fields': ('from_currency', 'to_currency', 'foreign_amount', 'myr_amount')
        }),
        ('Dispute Details', {
            'fields': ('reason', 'evidence', 'status')
        }),
        ('Seller Response', {
            'fields': ('seller_confirmation_status',),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('created_at', 'resolved_at'),
            'classes': ('collapse',)
        }),
    )

    inlines = [DisputeMessageInline, DisputeActivityLogInline]

    def get_buyer_email(self, obj):
        return obj.buyer.email

    get_buyer_email.short_description = 'Buyer'

    def get_seller_email(self, obj):
        return obj.seller.email

    get_seller_email.short_description = 'Seller'

    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'under_review': 'blue',
            'resolved': 'green',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )

    status_badge.short_description = 'Status'


@admin.register(DisputeResolution)
class DisputeResolutionAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_dispute_id', 'resolution_type', 'get_admin_name', 'resolved_at')
    list_filter = ('resolution_type', 'resolved_at')
    search_fields = ('dispute__id', 'resolved_by_admin__email', 'resolution_notes')
    readonly_fields = ('id', 'resolved_at')

    fieldsets = (
        ('Dispute Reference', {
            'fields': ('dispute',)
        }),
        ('Resolution', {
            'fields': ('resolution_type', 'buyer_refund_amount', 'seller_refund_amount', 'resolution_notes')
        }),
        ('Admin Info', {
            'fields': ('resolved_by_admin', 'resolved_at'),
            'classes': ('collapse',)
        }),
    )

    def get_dispute_id(self, obj):
        return f"Dispute #{obj.dispute.id}"

    get_dispute_id.short_description = 'Dispute'

    def get_admin_name(self, obj):
        if obj.resolved_by_admin:
            return obj.resolved_by_admin.email
        return "N/A"

    get_admin_name.short_description = 'Resolved By'


@admin.register(DisputeMessage)
class DisputeMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_dispute_id', 'sender', 'is_admin_message', 'created_at')
    list_filter = ('is_admin_message', 'created_at')
    search_fields = ('dispute__id', 'sender__email', 'message')
    readonly_fields = ('id', 'created_at', 'dispute', 'sender')

    fieldsets = (
        ('Dispute & Sender', {
            'fields': ('dispute', 'sender', 'is_admin_message')
        }),
        ('Message', {
            'fields': ('message',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def get_dispute_id(self, obj):
        return f"Dispute #{obj.dispute.id}"

    get_dispute_id.short_description = 'Dispute'


@admin.register(DisputeActivityLog)
class DisputeActivityLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_dispute_id', 'actor', 'action_preview', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('dispute__id', 'actor__email', 'action')
    readonly_fields = ('id', 'timestamp', 'dispute', 'actor')

    fieldsets = (
        ('Dispute & Actor', {
            'fields': ('dispute', 'actor')
        }),
        ('Action', {
            'fields': ('action',)
        }),
        ('Metadata', {
            'fields': ('timestamp',),
            'classes': ('collapse',)
        }),
    )

    def get_dispute_id(self, obj):
        return f"Dispute #{obj.dispute.id}"

    get_dispute_id.short_description = 'Dispute'

    def action_preview(self, obj):
        return obj.action[:50] + '...' if len(obj.action) > 50 else obj.action

    action_preview.short_description = 'Action'

