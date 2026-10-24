
from datetime import date

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.certificates.models import Certificate
from apps.audit.models import AuditLog
from apps.verification.models import VerificationAttempt


User = get_user_model()


class VerificationAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="verification_test_user",
            password="TestPass123!",
        )

    def create_certificate(self, number, certificate_status):
        return Certificate.objects.create(
            owner=self.user,
            title="Test Certificate",
            issuer="OneSmarter Inc.",
            certificate_number=number,
            recipient_name="Test Recipient",
            issue_date=date(2026, 10, 11),
            status=certificate_status,
        )

    def check_number(self, number):
        return self.client.post(
            "/api/verification/check/",
            {"certificate_number": number},
            format="json",
        )

    def test_verified_certificate_is_verified(self):
        self.create_certificate(
            "VERIFY-TEST-001",
            Certificate.Status.VERIFIED,
        )

        response = self.check_number("VERIFY-TEST-001")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["found"])
        self.assertEqual(response.data["verification_result"], "VERIFIED")
        self.assertEqual(response.data["status"], "VERIFIED")
        self.assertIn("certificate", response.data)

    def test_pending_certificate_is_not_verified_or_disclosed(self):
        self.create_certificate(
            "VERIFY-TEST-002",
            Certificate.Status.PENDING,
        )

        response = self.check_number("VERIFY-TEST-002")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["found"])
        self.assertEqual(response.data["verification_result"], "PENDING")
        self.assertEqual(response.data["status"], "PENDING")
        self.assertNotIn("certificate", response.data)

        public_response = self.client.get("/api/certificates/verify/VERIFY-TEST-002/")
        self.assertEqual(public_response.status_code, 200)
        self.assertEqual(public_response.data["verification_result"], "PENDING")
        self.assertNotIn("recipient_name", public_response.data)

    def test_rejected_certificate_is_not_verified_or_disclosed(self):
        self.create_certificate(
            "VERIFY-TEST-003",
            Certificate.Status.REJECTED,
        )

        response = self.check_number("VERIFY-TEST-003")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["found"])
        self.assertEqual(response.data["verification_result"], "REJECTED")
        self.assertEqual(response.data["status"], "REJECTED")
        self.assertNotIn("certificate", response.data)

        public_response = self.client.get("/api/certificates/verify/VERIFY-TEST-003/")
        self.assertEqual(public_response.status_code, 200)
        self.assertEqual(public_response.data["verification_result"], "REJECTED")
        self.assertNotIn("recipient_name", public_response.data)

    def test_revoked_certificate_is_not_verified_or_disclosed(self):
        self.create_certificate("VERIFY-REVOKED-001", Certificate.Status.REVOKED)
        response = self.check_number("VERIFY-REVOKED-001")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["verification_result"], "REVOKED")
        self.assertNotIn("certificate", response.data)

    def test_unknown_certificate(self):
        response = self.check_number("VERIFY-NOT-FOUND")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["found"])
        self.assertEqual(response.data["verification_result"], "NOT_FOUND")
        self.assertEqual(response.data["status"], "NOT_FOUND")
        self.assertNotIn("certificate", response.data)

    def test_certificate_number_is_trimmed_and_case_normalized(self):
        self.create_certificate(
            "VERIFY-SPACE-001",
            Certificate.Status.PENDING,
        )

        response = self.check_number("  verify-space-001  ")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["found"])
        self.assertEqual(
            response.data["certificate_number"],
            "VERIFY-SPACE-001",
        )

    def test_empty_certificate_number_is_rejected(self):
        response = self.check_number("   ")

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("found", response.data)

    def test_public_check_does_not_require_login(self):
        self.assertFalse(self.client.login(
            username="verification_test_user",
            password="TestPass123!",
        ) is False)

        self.client.logout()

        response = self.check_number("NO-SUCH-CERT")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["found"])
        self.assertEqual(response.data["verification_result"], "NOT_FOUND")

    def test_verification_attempt_is_recorded(self):
        self.create_certificate(
            "VERIFY-TEST-004",
            Certificate.Status.VERIFIED,
        )

        before = VerificationAttempt.objects.count()

        response = self.check_number("VERIFY-TEST-004")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            VerificationAttempt.objects.count(),
            before + 1,
        )

        attempt = VerificationAttempt.objects.latest("created_at")
        self.assertEqual(attempt.certificate_number, "VERIFY-TEST-004")
        self.assertEqual(attempt.result, VerificationAttempt.Result.VERIFIED)

    def test_both_public_verifiers_record_the_same_status_and_lookup_audit(self):
        certificate = self.create_certificate("VERIFY-AUDIT-001", Certificate.Status.PENDING)
        post_response = self.check_number(certificate.certificate_number)
        get_response = self.client.get(f"/api/certificates/verify/{certificate.certificate_number}/")
        self.assertEqual(post_response["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0")
        self.assertEqual(get_response["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0")
        attempts = list(VerificationAttempt.objects.filter(certificate=certificate).order_by("id"))
        self.assertEqual([row.result for row in attempts], ["PENDING", "PENDING"])
        self.assertEqual(
            AuditLog.objects.filter(
                action=AuditLog.Action.CERTIFICATE_LOOKUP_FAILED,
                target_id=str(certificate.pk),
            ).count(),
            2,
        )
