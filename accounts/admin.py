from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'name', 'role', 'is_active', 'account_status', 'created_at')
    list_filter = ('role', 'is_active', 'created_at')
    search_fields = ('email', 'username', 'name')
    readonly_fields = ('created_at', 'updated_at', 'last_login')

    fieldsets = (
        ('Personal Info', {
            'fields': ('email', 'username', 'name', 'password')
        }),
        ('Permissions & Role', {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Security', {
            'fields': ('failed_login_attempts', 'locked_until'),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at', 'last_login'),
            'classes': ('collapse',)
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2', 'name', 'role'),
        }),
    )

    ordering = ('-created_at',)

    def account_status(self, obj):
        """Display account lock status."""
        if obj.is_account_locked():
            return format_html('<span style="color: red;">🔒 Locked</span>')
        return format_html('<span style="color: green;">✓ Active</span>')

    account_status.short_description = 'Status'

    def get_fieldsets(self, request, obj=None):
        """Customize fieldsets for add vs change."""
        if obj is None:  # Adding new user
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)

