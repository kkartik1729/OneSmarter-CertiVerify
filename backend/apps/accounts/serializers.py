
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
import re
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from .models import UserProfile

User = get_user_model()


class ExistingUserTokenRefreshSerializer(TokenRefreshSerializer):
    """Apply normal SimpleJWT checks and reject refresh tokens for deleted users."""

    def validate(self, attrs):
        try:
            # Parse first so signature, token type, expiry, and blacklist checks
            # remain enforced before looking up the referenced account.
            refresh = RefreshToken(attrs["refresh"])
            user_id = refresh.get(api_settings.USER_ID_CLAIM)
            if user_id is None:
                raise InvalidToken("Refresh token does not identify an account.")

            # Lock the row through token issuance so a concurrent delete cannot
            # leave a newly refreshed session for an account that disappeared.
            with transaction.atomic():
                user = User.objects.select_for_update().get(
                    **{api_settings.USER_ID_FIELD: user_id}
                )
                if not user.is_active:
                    raise InvalidToken("Session expired. Please log in again.")
                return super().validate(attrs)
        except User.DoesNotExist as exc:
            raise InvalidToken("Session expired. Please log in again.") from exc
        except TokenError as exc:
            raise InvalidToken("Token is invalid or expired. Please log in again.") from exc


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
    )
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "password_confirm",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({
                "password_confirm": "Passwords do not match."
            })

        email = str(attrs.get("email", "")).strip().lower()
        if not email:
            raise serializers.ValidationError({
                "email": "Email address is required."
            })
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError({
                "email": "An account with this email already exists."
            })
        attrs["email"] = email
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")

        user = User(**validated_data)
        user.is_staff = False
        user.is_superuser = False
        user.set_password(password)
        user.save()

        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={"role": UserProfile.Role.USER},
        )
        if profile.role != UserProfile.Role.USER:
            profile.role = UserProfile.Role.USER
            profile.save(update_fields=["role", "updated_at"])
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    # Writable so that PATCH /accounts/me/ can update them
    first_name = serializers.CharField(source="user.first_name", required=False)
    last_name = serializers.CharField(source="user.last_name", required=False, allow_blank=True)
    role = serializers.SerializerMethodField()
    mfa_enabled = serializers.BooleanField(read_only=True)
    email_verified = serializers.BooleanField(read_only=True)
    has_usable_password = serializers.SerializerMethodField()
    is_google_user = serializers.SerializerMethodField()
    has_unclaimed_certificates = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "phone",
            "organization",
            "mfa_enabled",
            "email_verified",
            "has_usable_password",
            "is_google_user",
            "has_unclaimed_certificates",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "username",
            "email",
            "role",
            "mfa_enabled",
            "email_verified",
            "has_usable_password",
            "is_google_user",
            "has_unclaimed_certificates",
            "created_at",
        ]

    def get_has_usable_password(self, obj):
        return bool(obj.user and obj.user.has_usable_password())

    def get_is_google_user(self, obj):
        return bool(obj.google_sub)

    def get_has_unclaimed_certificates(self, obj):
        user = getattr(obj, "user", None)
        if not user or not user.email or getattr(obj, "email_verified", False):
            return False
        try:
            from apps.certificates.models import Certificate
            from django.db.models.functions import Lower, Trim
            return Certificate.objects.annotate(
                clean_recipient_email=Trim(Lower("recipient_email")),
            ).filter(
                clean_recipient_email=user.email.strip().lower(),
                owner__isnull=True,
                status=Certificate.Status.VERIFIED,
            ).exists()
        except Exception:
            return False

    def validate_organization(self, value):
        value = value.strip()
        if value and (not re.search(r"[^\W\d_]", value, re.UNICODE) or re.search(r"[^\w\s.,&'’()\-/+]", value, re.UNICODE) or re.search(r"\d", value)):
            raise serializers.ValidationError("Please enter a valid organization name.")
        return value

    def validate_phone(self, value):
        value = value.strip()
        if self.instance and value == self.instance.phone:
            return value
        if not value:
            return ""
        normalized = re.sub(r"[\s().-]", "", value)
        if not re.fullmatch(r"\+[1-9]\d{6,14}", normalized):
            raise serializers.ValidationError("Please enter a valid phone number for the selected country.")
        # India has a fixed 10-digit national subscriber number. Other countries
        # are validated against libphonenumber metadata in the shared UI, while
        # this API enforces the universal E.164 storage shape for every region.
        if normalized.startswith("+91") and len(normalized) != 13:
            raise serializers.ValidationError("Please enter a valid phone number for the selected country.")
        return normalized

    def get_role(self, obj):
        if getattr(obj.user, "is_superuser", False) or getattr(obj.user, "is_staff", False):
            return UserProfile.Role.ADMIN
        return obj.role

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        user = instance.user
        if "first_name" in user_data:
            user.first_name = user_data["first_name"]
        if "last_name" in user_data:
            user.last_name = user_data["last_name"]
        if user_data:
            user.save(update_fields=[k for k in user_data.keys()])
        return super().update(instance, validated_data)


class AdminUserSerializer(serializers.ModelSerializer):
    """Read-only serializer for admin user listing. No passwords or secrets."""
    role = serializers.SerializerMethodField()
    mfa_enabled = serializers.SerializerMethodField()
    email_verified = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "is_active",
            "mfa_enabled",
            "email_verified",
            "date_joined",
        ]

    def get_role(self, obj):
        if getattr(obj, "is_superuser", False) or getattr(obj, "is_staff", False):
            return "ADMIN"
        try:
            return obj.profile.role
        except Exception:
            return "USER"

    def get_email_verified(self, obj):
        try:
            return obj.profile.email_verified
        except Exception:
            return False

    def get_mfa_enabled(self, obj):
        try:
            return obj.profile.mfa_enabled
        except Exception:
            return False

    def get_full_name(self, obj):
        name = f"{obj.first_name} {obj.last_name}".strip()
        return name or obj.username

