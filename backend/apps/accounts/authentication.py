from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from .models import UserProfile

User = get_user_model()


def issue_user_refresh_token(user):
    """Issue a refresh token bound to the precise password-change version."""
    refresh = RefreshToken.for_user(user)
    changed_at = UserProfile.objects.filter(user=user).values_list(
        "password_changed_at", flat=True
    ).first()
    refresh["pwdv"] = changed_at.isoformat(timespec="microseconds") if changed_at else ""
    return refresh


class SessionInvalidatingJWTAuthentication(JWTAuthentication):
    """Reject access tokens issued before a user password reset."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        # Email ownership is required before any protected API can be used.
        profile_state = UserProfile.objects.filter(user=user).values_list(
            "email_verified", "mfa_enabled"
        ).first()
        email_verified = profile_state[0] if profile_state else False
        mfa_enabled = profile_state[1] if profile_state else False
        if not email_verified:
            raise AuthenticationFailed(
                "Verify your email address before accessing your account.",
                code="email_not_verified",
            )
        if user.has_usable_password() and not mfa_enabled:
            raise AuthenticationFailed(
                "Complete two-factor authentication setup before accessing your account.",
                code="mfa_setup_required",
            )
        issued_at = validated_token.get("iat")
        if issued_at is None:
            raise AuthenticationFailed("Token is invalid.", code="token_not_valid")
        changed_at = User.objects.filter(pk=user.pk).values_list(
            "profile__password_changed_at", flat=True
        ).first()
        if changed_at:
            if "pwdv" in validated_token:
                token_password_version = validated_token.get("pwdv")
                current_password_version = changed_at.isoformat(timespec="microseconds")
                if token_password_version != current_password_version:
                    raise AuthenticationFailed("Session expired. Please sign in again.", code="token_not_valid")
            elif int(issued_at) < int(changed_at.timestamp()):
                # Compatibility for tokens issued before the precise version claim.
                raise AuthenticationFailed("Session expired. Please sign in again.", code="token_not_valid")
        return user
