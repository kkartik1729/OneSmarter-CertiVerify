
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Notification.objects.filter(
            recipient=self.request.user
        ).select_related("certificate")

        raw_filter = self.request.query_params.get("is_read")
        if raw_filter is None or raw_filter.strip() == "":
            return queryset
        read_filter = raw_filter.strip().lower()
        values = {"true": True, "1": True, "false": False, "0": False}
        if read_filter not in values:
            raise ValidationError({"is_read": "Use true, false, 1, or 0."})
        queryset = queryset.filter(is_read=values[read_filter])

        return queryset


class UnreadNotificationCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).count()

        return Response({"unread_count": count})


class MarkNotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        notification = get_object_or_404(
            Notification,
            pk=pk,
            recipient=request.user,
        )

        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])

        return Response(NotificationSerializer(notification).data)


class MarkAllNotificationsReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).update(is_read=True)

        return Response({
            "message": "All notifications marked as read.",
            "updated_count": updated_count,
        }, status=status.HTTP_200_OK)
