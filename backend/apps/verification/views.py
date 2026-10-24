
from django.db import transaction

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.certificates.models import Certificate
from apps.certificates.permissions import is_certiverify_admin

from .models import VerificationAttempt
from .services import record_verification_attempt
from .authentication import OptionalJWTAuthentication
from .serializers import (
    VerificationAttemptSerializer,
    VerificationCheckSerializer,
)


class VerificationCheckView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [OptionalJWTAuthentication]

    def post(self, request):
        serializer = VerificationCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        certificate_number = serializer.validated_data[
            "certificate_number"
        ]

        certificate = Certificate.objects.filter(
            certificate_number=certificate_number
        ).first()
        with transaction.atomic():
            attempt, result, message, is_verified = record_verification_attempt(
                certificate, certificate_number, request
            )

        response_data = {
            "certificate_number": certificate_number,
            "found": certificate is not None,
            "verification_result": result,
            "status": result,
            "message": message,
        }

        if is_verified:
            response_data["certificate"] = {
                "title": certificate.title,
                "issuer": certificate.issuer,
                "issue_date": certificate.issue_date,
            }

        response = Response(response_data, status=status.HTTP_200_OK)
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response


class VerificationHistoryView(generics.ListAPIView):
    serializer_class = VerificationAttemptSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = VerificationAttempt.objects.select_related(
            "requested_by",
            "certificate",
        ).order_by("-created_at", "-id")

        if is_certiverify_admin(self.request.user):
            return queryset

        return queryset.filter(requested_by=self.request.user)
