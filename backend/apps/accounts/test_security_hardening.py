import hashlib
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.accounts.client_ip import get_client_ip
from apps.accounts.models import UserProfile
from apps.audit.models import AuditLog
from apps.certificates.models import Certificate
from apps.certificates.permissions import is_certiverify_admin
from apps.certificates.serializers import CertificateSerializer
from apps.verification.services import certificate_artifacts_are_intact

User = get_user_model()


class TrustedClientIPTests(SimpleTestCase):
    @override_settings(TRUSTED_PROXY_IPS=())
    def test_untrusted_forwarded_header_is_ignored(self):
        request = RequestFactory().get(
            "/", REMOTE_ADDR="192.0.2.10", HTTP_X_FORWARDED_FOR="203.0.113.9"
        )
        self.assertEqual(get_client_ip(request), "192.0.2.10")

    @override_settings(TRUSTED_PROXY_IPS=("10.0.0.0/8",))
    def test_trusted_proxy_chain_resolves_first_untrusted_hop(self):
        request = RequestFactory().get(
            "/", REMOTE_ADDR="10.1.2.3",
            HTTP_X_FORWARDED_FOR="198.51.100.20, 10.3.4.5",
        )
        self.assertEqual(get_client_ip(request), "198.51.100.20")


class AdminRoleAuthorityTests(SimpleTestCase):
    def test_stale_profile_role_cannot_grant_admin_access(self):
        user = SimpleNamespace(
            is_authenticated=True, is_staff=False, is_superuser=False
        )
        self.assertFalse(is_certiverify_admin(user))


class SecurityAndIntegrityAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="hardening-user", email="hardening@example.test", password="CorrectHorse9!"
        )
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.profile.email_verified = True
        self.profile.mfa_enabled = False
        self.profile.save(update_fields=["email_verified", "mfa_enabled", "updated_at"])

    def test_password_account_without_mfa_cannot_use_existing_access_token(self):
        token = AccessToken.for_user(self.user)
        response = self.client.get(
            "/api/accounts/me/", HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("two-factor", response.data["detail"].lower())

    def test_logout_blacklists_refresh_token_and_is_idempotent(self):
        refresh = RefreshToken.for_user(self.user)
        response = self.client.post(
            "/api/accounts/logout/", {"refresh": str(refresh)}, format="json"
        )
        self.assertEqual(response.status_code, 205)
        with self.assertRaises(TokenError):
            RefreshToken(str(refresh)).check_blacklist()
        self.assertEqual(
            self.client.post(
                "/api/accounts/logout/", {"refresh": str(refresh)}, format="json"
            ).status_code,
            205,
        )

    def test_registration_does_not_reveal_existing_email_or_username(self):
        payload = {
            "username": self.user.username,
            "email": self.user.email,
            "first_name": "Attempt",
            "last_name": "Duplicate",
            "password": "NewPassword@123",
            "password_confirm": "NewPassword@123",
        }
        with patch("apps.accounts.views.send_email_verification_otp_email") as sender:
            response = self.client.post("/api/accounts/register/", payload, format="json")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(
            response.data["detail"],
            "If registration can be completed, verification instructions will be sent to the matching email.",
        )
        self.assertNotIn("email", response.data)
        self.assertNotIn("verification_email_sent", response.data)
        sender.assert_not_called()

    def test_dashboard_get_does_not_claim_certificates_as_a_side_effect(self):
        certificate = Certificate.objects.create(
            owner=None,
            recipient_email=self.user.email,
            title="Unclaimed record",
            issuer="OneSmarter",
            certificate_number="OSCV-2026-DASHBOARD01",
            recipient_name="Test Recipient",
            issue_date="2026-01-01",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/dashboard/")

        self.assertEqual(response.status_code, 200)
        certificate.refresh_from_db()
        self.assertIsNone(certificate.owner_id)

    def test_issued_certificate_content_cannot_be_changed_in_detail_api(self):
        certificate = Certificate.objects.create(
            owner=self.user,
            title="Original Title",
            issuer="OneSmarter",
            certificate_number="OSCV-2026-ABCDEF12",
            recipient_name="Test Recipient",
            issue_date="2026-01-01",
        )
        request = SimpleNamespace(method="PATCH")
        serializer = CertificateSerializer(
            certificate,
            data={"recipient_name": "Changed Name"},
            partial=True,
            context={"request": request},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("detail", serializer.errors)

    def test_verified_file_hash_is_checked_before_authenticity_claim(self):
        with tempfile.TemporaryDirectory() as media_dir:
            with override_settings(MEDIA_ROOT=Path(media_dir), MEDIA_URL="/media/"):
                content = b"certificate image bytes"
                certificate = Certificate.objects.create(
                    owner=self.user,
                    title="Integrity Test",
                    issuer="OneSmarter",
                    certificate_number="OSCV-2026-ABCDEF13",
                    recipient_name="Test Recipient",
                    issue_date="2026-01-01",
                    status=Certificate.Status.VERIFIED,
                    file_sha256=hashlib.sha256(content).hexdigest(),
                )
                certificate.file.save("certificate.png", ContentFile(content), save=True)
                self.assertTrue(certificate_artifacts_are_intact(certificate))
                with certificate.file.storage.open(certificate.file.name, "wb") as stored:
                    stored.write(b"altered certificate")
                self.assertFalse(certificate_artifacts_are_intact(certificate))

    def test_audit_log_entries_reject_update_and_delete(self):
        entry = AuditLog.objects.create(
            actor=self.user,
            action=AuditLog.Action.USER_LOGIN,
            target_type="User",
            target_id=str(self.user.pk),
        )
        with self.assertRaises(ValidationError):
            entry.save()
        with self.assertRaises(ValidationError):
            entry.delete()
        with self.assertRaises(ValidationError):
            AuditLog.objects.filter(pk=entry.pk).update(description="altered")
        with self.assertRaises(ValidationError):
            AuditLog.objects.filter(pk=entry.pk).delete()
