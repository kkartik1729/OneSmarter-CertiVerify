
from rest_framework.permissions import BasePermission


def is_certiverify_admin(user):
    """
    Return True for Django staff/superusers or users
    whose UserProfile role is ADMIN.
    """
    if not user or not user.is_authenticated:
        return False

    # Django admin and superuser accounts
    if user.is_staff or user.is_superuser:
        return True

    # Application-level admin role
    try:
        return user.profile.role == "ADMIN"
    except Exception:
        return False


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
