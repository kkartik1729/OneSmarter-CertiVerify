from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "actor", "target_type", "target_id", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("target_type", "target_id", "description")
    readonly_fields = tuple(field.name for field in AuditLog._meta.fields)
    ordering = ("-created_at", "-id")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
