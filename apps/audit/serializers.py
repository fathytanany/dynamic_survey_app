from rest_framework import serializers

from apps.audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "user",
            "user_email",
            "action",
            "model_name",
            "object_id",
            "changes",
            "ip_address",
            "user_agent",
            "timestamp",
        ]
        read_only_fields = fields

    def get_user_email(self, obj):
        return obj.user.email if obj.user_id else None
