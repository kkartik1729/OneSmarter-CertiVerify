from datetime import date

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.audit.models import AuditLog
from apps.certificates.models import Certificate
from apps.notifications.models import Notification


User = get_user_model()


class CertificateNotificationTests(APITestCase):
    """Test that manual certificate review is disabled."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username="certificate_owner_test",
            password="TestPass123!",
        )
        self.admin = User.objects.create_superuser(
            username="certificate_review_admin",
            email="certificate-review@example.com",
            password="TestPass123!",
        )

    def create_pending_certificate(self, number):
        return Certificate.objects.create(
            owner=self.owner,
            title="Notification Test Certificate",
            issuer="OneSmarter Inc.",
            certificate_number=number,
            recipient_name="Test Recipient",
            issue_date=date(2026, 10, 11),
            status=Certificate.Status.PENDING,
        )

    def test_admin_cannot_manually_approve_certificate(self):
        certificate = self.create_pending_certificate(
            "NOTIFY-APPROVE-001"
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f"/api/certificates/{certificate.id}/review/",
            {"status": "VERIFIED"},
            format="json",
        )

        self.assertEqual(response.status_code, 405)

        certificate.refresh_from_db()
        self.assertEqual(
            certificate.status,
            Certificate.Status.PENDING,
        )

        self.assertFalse(
            Notification.objects.filter(
                certificate=certificate,
                notification_type=(
                    Notification.NotificationType.CERTIFICATE_APPROVED
                ),
            ).exists()
        )

        self.assertFalse(
            AuditLog.objects.filter(
                actor=self.admin,
                action=AuditLog.Action.CERTIFICATE_APPROVED,
                target_id=str(certificate.id),
            ).exists()
        )

    def test_admin_cannot_manually_reject_certificate(self):
        certificate = self.create_pending_certificate(
            "NOTIFY-REJECT-001"
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f"/api/certificates/{certificate.id}/review/",
            {
                "status": "REJECTED",
                "rejection_reason": "Test rejection reason",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 405)

        certificate.refresh_from_db()
        self.assertEqual(
            certificate.status,
            Certificate.Status.PENDING,
        )

        self.assertFalse(
            Notification.objects.filter(
                certificate=certificate,
                notification_type=(
                    Notification.NotificationType.CERTIFICATE_REJECTED
                ),
            ).exists()
        )

        self.assertFalse(
            AuditLog.objects.filter(
                actor=self.admin,
                action=AuditLog.Action.CERTIFICATE_REJECTED,
                target_id=str(certificate.id),
            ).exists()
        )

    def test_repeated_review_attempts_do_not_change_certificate(self):
        certificate = self.create_pending_certificate(
            "NOTIFY-ONCE-001"
        )
        self.client.force_authenticate(user=self.admin)

        first_response = self.client.patch(
            f"/api/certificates/{certificate.id}/review/",
            {"status": "VERIFIED"},
            format="json",
        )

        self.assertEqual(first_response.status_code, 405)

        notifications_before = Notification.objects.filter(
            certificate=certificate
        ).count()

        second_response = self.client.patch(
            f"/api/certificates/{certificate.id}/review/",
            {
                "status": "REJECTED",
                "rejection_reason": "Second attempt",
            },
            format="json",
        )

        self.assertEqual(second_response.status_code, 405)

        certificate.refresh_from_db()
        self.assertEqual(
            certificate.status,
            Certificate.Status.PENDING,
        )
        self.assertEqual(
            Notification.objects.filter(
                certificate=certificate
            ).count(),
            notifications_before,
        )
