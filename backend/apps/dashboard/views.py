
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.certificates.models import Certificate
from apps.certificates.permissions import is_certiverify_admin
from apps.verification.models import VerificationAttempt

import datetime

User = get_user_model()


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        is_admin = is_certiverify_admin(request.user)

        certificates = Certificate.objects.all()

        if not is_admin:
            certificates = certificates.filter(owner=request.user)

        stats = certificates.aggregate(
            total=Count("id"),
            verified=Count(
                "id",
                filter=Q(status="VERIFIED"),
            ),
            pending=Count(
                "id",
                filter=Q(status="PENDING"),
            ),
            rejected=Count(
                "id",
                filter=Q(status="REJECTED"),
            ),
        )

        recent_certificates = certificates.order_by(
            "-created_at"
        )[:5]

        recent_data = [
            {
                "id": certificate.id,
                "certificate_number": certificate.certificate_number,
                "title": certificate.title,
                "issuer": certificate.issuer,
                "recipient_name": certificate.recipient_name,
                "status": certificate.status,
                "created_at": certificate.created_at,
            }
            for certificate in recent_certificates
        ]

        # User verification metrics
        user_attempts = (
            VerificationAttempt.objects.all()
            if is_admin
            else VerificationAttempt.objects.filter(requested_by=request.user)
        )
        total_searches = user_attempts.count()

        # Distinct certificate records found through user's searches
        user_found_attempts = user_attempts.filter(
            result__in=[
                VerificationAttempt.Result.FOUND,
                VerificationAttempt.Result.VERIFIED,
            ]
        )
        distinct_verified = (
            user_found_attempts.values("certificate_number")
            .distinct()
            .count()
        )

        recent_user_searches = [
            {
                "id": v.id,
                "certificate_number": v.certificate_number,
                "result": v.result,
                "verification_result": (
                    "VERIFIED"
                    if v.result in (
                        VerificationAttempt.Result.FOUND,
                        VerificationAttempt.Result.VERIFIED,
                    )
                    else "NOT_VERIFIED"
                ),
                "status": (
                    "VERIFIED"
                    if v.result in (
                        VerificationAttempt.Result.FOUND,
                        VerificationAttempt.Result.VERIFIED,
                    )
                    else "NOT_FOUND"
                ),
                "certificate_title": (
                    v.certificate.title if v.certificate else None
                ),
                "created_at": v.created_at,
            }
            for v in user_attempts.select_related("certificate").order_by("-created_at")[:5]
        ]

        response = {
            "role": "ADMIN" if is_admin else "USER",
            "my_certificates": stats["total"],
            "verified_records": distinct_verified,
            "verification_searches": total_searches,
            "statistics": {
                **stats,
                "verified_records": distinct_verified,
                "verification_searches": total_searches,
            },
            "recent_certificates": recent_data,
            "recent_verification_searches": recent_user_searches,
        }

        if is_admin:
            # Admin-only metrics
            total_users = User.objects.count()
            verification_stats = VerificationAttempt.objects.aggregate(
                total=Count("id"),
                found=Count("id", filter=Q(result="FOUND")),
                not_found=Count("id", filter=Q(result="NOT_FOUND")),
            )

            # Last 30 days of certificate creation (daily counts)
            thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
            cert_trend = (
                Certificate.objects.filter(created_at__gte=thirty_days_ago)
                .annotate(day=TruncDate("created_at"))
                .values("day")
                .annotate(count=Count("id"))
                .order_by("day")
            )
            cert_trend_list = [
                {"date": str(x["day"]), "count": x["count"]}
                for x in cert_trend
            ]

            # Last 30 days of verification attempts (daily counts)
            verify_trend = (
                VerificationAttempt.objects.filter(created_at__gte=thirty_days_ago)
                .annotate(day=TruncDate("created_at"))
                .values("day")
                .annotate(
                    total=Count("id"),
                    found=Count("id", filter=Q(result="FOUND")),
                    not_found=Count("id", filter=Q(result="NOT_FOUND")),
                )
                .order_by("day")
            )
            verify_trend_list = [
                {
                    "date": str(x["day"]),
                    "total": x["total"],
                    "found": x["found"],
                    "not_found": x["not_found"],
                }
                for x in verify_trend
            ]

            # Certificates per issuer
            issuer_breakdown = (
                Certificate.objects.values("issuer")
                .annotate(count=Count("id"))
                .order_by("-count")[:10]
            )
            issuer_list = [
                {"issuer": x["issuer"], "count": x["count"]}
                for x in issuer_breakdown
            ]

            # Recent verification attempts
            recent_verifications = VerificationAttempt.objects.order_by(
                "-created_at"
            ).select_related("requested_by")[:10]
            recent_verify_data = [
                {
                    "id": v.id,
                    "certificate_number": v.certificate_number,
                    "result": v.result,
                    "created_at": v.created_at,
                    "requested_by": (
                        v.requested_by.username
                        if v.requested_by
                        else None
                    ),
                }
                for v in recent_verifications
            ]

            response["admin_stats"] = {
                "total_users": total_users,
                "total_certificates": stats["total"],
                "total_verification_attempts": verification_stats["total"],
                "successful_verifications": verification_stats["found"],
                "unsuccessful_verifications": verification_stats["not_found"],
                "certificate_trend": cert_trend_list,
                "verification_trend": verify_trend_list,
                "issuer_breakdown": issuer_list,
                "recent_verifications": recent_verify_data,
            }

        return Response(response)
