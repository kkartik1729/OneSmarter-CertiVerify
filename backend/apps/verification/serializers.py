
from rest_framework import serializers

from .models import VerificationAttempt


class VerificationCheckSerializer(serializers.Serializer):
    certificate_number = serializers.CharField(
        max_length=100,
        trim_whitespace=True,
    )

    def validate_certificate_number(self, value):
        value = value.strip().upper()

        if not value:
            raise serializers.ValidationError(
                "Certificate number is required."
            )

        return value


class VerificationAttemptSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.CharField(
        source="requested_by.username",
        read_only=True,
        default=None,
    )
    certificate_title = serializers.CharField(
        source="certificate.title",
        read_only=True,
        default=None,
    )
    verification_result = serializers.SerializerMethodField()

    class Meta:
        model = VerificationAttempt
        fields = [
            "id",
            "certificate_number",
            "result",
            "verification_result",
            "certificate_title",
            "requested_by_username",
            "created_at",
        ]
        read_only_fields = fields

    def get_verification_result(self, obj):
        if obj.result in (VerificationAttempt.Result.FOUND, VerificationAttempt.Result.VERIFIED):
            return "VERIFIED"
        return "NOT_VERIFIED"

