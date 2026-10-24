
from rest_framework import serializers

from .models import VerificationAttempt


class VerificationCheckSerializer(serializers.Serializer):
    certificate_number = serializers.CharField(
        max_length=100,
        trim_whitespace=True,
    )

    def validate_certificate_number(self, value):
        return value.upper()


class VerificationAttemptSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.CharField(
        source="requested_by.username",
        read_only=True,
        default=None,
    )
    certificate_title = serializers.SerializerMethodField()
    verification_result = serializers.SerializerMethodField()
    result = serializers.SerializerMethodField()

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

    def get_result(self, obj):
        return self._state(obj)[0]

    def get_verification_result(self, obj):
        return self.get_result(obj)

    def get_certificate_title(self, obj):
        _state, _message, is_verified = self._state(obj)
        return obj.certificate.title if is_verified and obj.certificate_id else None

    @staticmethod
    def _state(obj):
        from .services import certificate_verification_state
        return certificate_verification_state(obj.certificate)

