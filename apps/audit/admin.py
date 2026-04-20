from django.contrib import admin

from apps.audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "action", "model_name", "object_id", "user", "ip_address")
    list_filter = ("action", "model_name")
    search_fields = ("model_name", "object_id", "user__email", "ip_address")
    date_hierarchy = "timestamp"
    readonly_fields = (
        "id", "user", "action", "model_name", "object_id",
        "changes", "ip_address", "user_agent", "timestamp",
    )
    ordering = ("-timestamp",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
