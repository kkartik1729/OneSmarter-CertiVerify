
from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    certificate_number = serializers.CharField(
        source="certificate.certificate_number",
        read_only=True,
        allow_null=True,
        default=None,
    )

    class Meta:
        model = Notification
        fields = [
            "id",
            "notification_type",
            "title",
            "message",
            "certificate",
            "certificate_number",
            "is_read",
            "created_at",
        ]
        read_only_fields = fields
