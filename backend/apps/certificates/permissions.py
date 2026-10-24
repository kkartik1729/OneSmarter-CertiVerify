
from rest_framework.permissions import BasePermission


def is_certiverify_admin(user):
    """Django's staff/superuser flags are the authoritative admin grants."""
    if not user or not user.is_authenticated:
        return False
    return bool(user.is_staff or user.is_superuser)


class IsCertiVerifyAdmin(BasePermission):
    """
    Only CertiVerify administrators can access the view.
    """

    message = "Only administrators can perform this action."

    def has_permission(self, request, view):
        return is_certiverify_admin(request.user)


class IsOwnerOrCertiVerifyAdmin(BasePermission):
    """
    Certificate owners and administrators can view a certificate.
    Only administrators can update or modify certificate records.
    """

    message = "You do not have permission to access or modify this certificate."

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in ("GET", "HEAD", "OPTIONS"):
            return (
                is_certiverify_admin(request.user)
                or obj.owner_id == request.user.id
            )

        return is_certiverify_admin(request.user)


class HasCompletedMFAIfPasswordUser(BasePermission):
    """
    Enforces that users with a manual password must have completed TOTP MFA enrollment
    before accessing protected application endpoints.
    Users authenticated through trusted Google Sign-In who have not set up a local password
    are permitted without TOTP MFA.
    """

    message = "Two-factor authentication enrollment is required before accessing protected resources."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return True

        # Only password-bearing accounts require TOTP MFA
        if user.has_usable_password():
            try:
                return bool(user.profile.mfa_enabled)
            except Exception:
                return False
        return True
