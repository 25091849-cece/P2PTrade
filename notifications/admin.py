from django.contrib import admin
from django.utils.html import format_html
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_user_email', 'notification_type', 'read_status', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('user__email', 'message')
    readonly_fields = ('id', 'created_at')

    fieldsets = (
        ('User', {
            'fields': ('user', 'is_read')
        }),
        ('Notification', {
            'fields': ('notification_type', 'message', 'related_id')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',)
        }),
    )

    def get_user_email(self, obj):
        return obj.user.email

    get_user_email.short_description = 'User'

    def read_status(self, obj):
        if obj.is_read:
            return format_html('<span style="color: gray;">✓ Read</span>')
        return format_html('<span style="color: blue;">● Unread</span>')

    read_status.short_description = 'Status'

    actions = ['mark_as_read', 'mark_as_unread']

    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f'{updated} notification(s) marked as read.')

    mark_as_read.short_description = 'Mark selected as read'

    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, f'{updated} notification(s) marked as unread.')

    mark_as_unread.short_description = 'Mark selected as unread'

