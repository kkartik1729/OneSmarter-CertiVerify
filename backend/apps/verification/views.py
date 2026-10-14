
from django.db import transaction

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.audit.services import log_action
from apps.certificates.models import Certificate
from apps.certificates.permissions import is_certiverify_admin

from .models import VerificationAttempt
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

        # Only database existence determines the result.
        # Certificate approval status does not affect FOUND.
        certificate = Certificate.objects.filter(
            certificate_number=certificate_number
        ).first()

        if certificate is None:
            result = VerificationAttempt.Result.NOT_FOUND
        else:
            result = VerificationAttempt.Result.FOUND

        with transaction.atomic():
            attempt = VerificationAttempt.objects.create(
                certificate=certificate,
                certificate_number=certificate_number,
                result=result,
                requested_by=(
                    request.user
                    if request.user.is_authenticated
                    else None
                ),
            )

            log_action(
                action=(
                    AuditLog.Action.CERTIFICATE_VERIFIED
                    if certificate is not None
                    else AuditLog.Action.OTHER
                ),
                actor=(
                    request.user
                    if request.user.is_authenticated
                    else None
                ),
                target_type="Certificate",
                target_id=certificate.id if certificate else "",
                description=f"Certificate lookup result: {result}",
                metadata={
                    "certificate_number": certificate_number,
                    "result": result,
                    "found": certificate is not None,
                },
                ip_address=request.META.get("REMOTE_ADDR"),
            )

        response_data = {
            "certificate_number": certificate_number,
            "found": certificate is not None,
            "verification_result": result,
            "status": result,
            "message": (
                "Certificate found in the database."
                if certificate is not None
                else "Certificate was not found in the database."
            ),
            "verification_attempt_id": attempt.id,
        }

        if certificate is not None:
            response_data["certificate"] = {
                "title": certificate.title,
                "issuer": certificate.issuer,
                "issue_date": certificate.issue_date,
            }

        return Response(response_data, status=status.HTTP_200_OK)


class VerificationHistoryView(generics.ListAPIView):
    serializer_class = VerificationAttemptSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = VerificationAttempt.objects.select_related(
            "requested_by",
            "certificate",
        ).order_by("-created_at")

        if is_certiverify_admin(self.request.user):
            return queryset

        return queryset.filter(requested_by=self.request.user)
