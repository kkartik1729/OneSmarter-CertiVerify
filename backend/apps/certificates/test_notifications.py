from datetime import date

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.audit.models import AuditLog
from apps.certificates.models import Certificate
from apps.notifications.models import Notification


User = get_user_model()


class CertificateNotificationTests(APITestCase):
    """Certificate review transitions notify and audit their owner-facing outcome."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username="certificate_owner_test",
            email="certificate-owner@example.test",
            password="TestPass123!",
        )
        self.admin = User.objects.create_superuser(
            username="certificate_review_admin",
            email="certificate-review@example.test",
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

    def test_admin_can_approve_pending_certificate_and_notify_owner(self):
        certificate = self.create_pending_certificate("NOTIFY-APPROVE-001")
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(
            f"/api/certificates/{certificate.id}/review/",
            {"status": "VERIFIED"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        certificate.refresh_from_db()
        self.assertEqual(certificate.status, Certificate.Status.VERIFIED)
        self.assertTrue(Notification.objects.filter(
            recipient=self.owner,
            certificate=certificate,
            notification_type=Notification.NotificationType.CERTIFICATE_APPROVED,
        ).exists())
        self.assertTrue(AuditLog.objects.filter(
            actor=self.admin,
            action=AuditLog.Action.CERTIFICATE_APPROVED,
            target_id=str(certificate.id),
        ).exists())

    def test_admin_can_reject_pending_certificate_with_reason_and_notify_owner(self):
        certificate = self.create_pending_certificate("NOTIFY-REJECT-001")
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(
            f"/api/certificates/{certificate.id}/review/",
            {"status": "REJECTED", "rejection_reason": "Test rejection reason"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        certificate.refresh_from_db()
        self.assertEqual(certificate.status, Certificate.Status.REJECTED)
        self.assertEqual(certificate.rejection_reason, "Test rejection reason")
        self.assertTrue(Notification.objects.filter(
            recipient=self.owner,
            certificate=certificate,
            notification_type=Notification.NotificationType.CERTIFICATE_REJECTED,
        ).exists())
        self.assertTrue(AuditLog.objects.filter(
            actor=self.admin,
            action=AuditLog.Action.CERTIFICATE_REJECTED,
            target_id=str(certificate.id),
        ).exists())

    def test_repeated_same_transition_is_idempotent_and_revoked_is_terminal(self):
        certificate = self.create_pending_certificate("NOTIFY-ONCE-001")
        self.client.force_authenticate(user=self.admin)
        url = f"/api/certificates/{certificate.id}/review/"
        first = self.client.patch(url, {"status": "VERIFIED"}, format="json")
        self.assertEqual(first.status_code, 200)
        notification_count = Notification.objects.filter(certificate=certificate).count()
        second = self.client.patch(url, {"status": "VERIFIED"}, format="json")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Notification.objects.filter(certificate=certificate).count(), notification_count)

        revoke = self.client.patch(
            url,
            {"status": "REVOKED", "rejection_reason": "Withdrawn"},
            format="json",
        )
        self.assertEqual(revoke.status_code, 200)
        reactivate = self.client.patch(url, {"status": "VERIFIED"}, format="json")
        self.assertEqual(reactivate.status_code, 409)
        certificate.refresh_from_db()
        self.assertEqual(certificate.status, Certificate.Status.REVOKED)
