"""
Admin-only views for user management.
These endpoints enforce is_certiverify_admin permission.
Passwords, OTPs, and TOTP secrets are never exposed.
"""
from django.contrib.auth import get_user_model
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.certificates.permissions import IsCertiVerifyAdmin, is_certiverify_admin
from .models import UserProfile
from .serializers import AdminUserSerializer

User = get_user_model()


class AdminUserListView(generics.ListAPIView):
    """GET /api/accounts/admin/users/ — list all users (admin only)."""
    serializer_class = AdminUserSerializer
    permission_classes = [IsAuthenticated, IsCertiVerifyAdmin]

    def get_queryset(self):
        qs = User.objects.select_related("profile").order_by("-date_joined")

        # Search
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                **{"username__icontains": search}
            ) | qs.filter(
                **{"email__icontains": search}
            ) | qs.filter(
                **{"first_name__icontains": search}
            ) | qs.filter(
                **{"last_name__icontains": search}
            )

        # Role filter
        role = self.request.query_params.get("role", "").strip().upper()
        if role in ("ADMIN", "USER"):
            qs = qs.filter(profile__role=role)

        return qs.distinct()


class AdminUserDetailView(APIView):
    """GET /api/accounts/admin/users/<pk>/ — view one user (admin only)."""
    permission_classes = [IsAuthenticated, IsCertiVerifyAdmin]

    def get(self, request, pk):
        try:
            user = User.objects.select_related("profile").get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = AdminUserSerializer(user)
        return Response(serializer.data)
