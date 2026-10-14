
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.certificates.permissions import is_certiverify_admin

from .models import AuditLog
from .serializers import AuditLogSerializer


class IsAuditAdministrator(IsAuthenticated):
    message = "Only administrators can view audit logs."

    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and is_certiverify_admin(request.user)
        )


class AuditLogListView(generics.ListAPIView):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuditAdministrator]

    def get_queryset(self):
        queryset = AuditLog.objects.select_related("actor").all()

        action = self.request.query_params.get("action")
        if action:
            queryset = queryset.filter(action=action)

        target_type = self.request.query_params.get("target_type")
        if target_type:
            queryset = queryset.filter(target_type=target_type)

        return queryset
