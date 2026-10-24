import hashlib
import json
import re
from datetime import timedelta
from unittest import skipUnless
from unittest.mock import Mock, patch

import pyotp
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import EmailVerificationToken, MFARecoveryToken, PasswordResetRequest, PasswordResetToken, UserProfile
from apps.certificates.models import Certificate

User = get_user_model()


class AccountsAuthAndMFATestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Create standard user
        self.user = User.objects.create_user(
            username="normaluser",
            email="normaluser@example.com",
            password="Password@123",
            first_name="Normal",
            last_name="User",
        )
        self.user.profile.email_verified = True
        self.user.profile.email_verified_at = timezone.now()
        self.user.profile.save(update_fields=["email_verified", "email_verified_at", "updated_at"])

        # Create admin user
        self.admin = User.objects.create_superuser(
            username="superadmin",
            email="superadmin@example.com",
            password="AdminPassword@123",
            first_name="Super",
            last_name="Admin",
        )
        self.admin.profile.email_verified = True
        self.admin.profile.email_verified_at = timezone.now()
        self.admin.profile.save(update_fields=["email_verified", "email_verified_at", "updated_at"])

        # Create staff user
        self.staff = User.objects.create_user(
            username="staffadmin",
            email="staffadmin@example.com",
            password="StaffPassword@123",
            is_staff=True,
            first_name="Staff",
            last_name="Admin",
        )
        self.staff.profile.email_verified = True
        self.staff.profile.email_verified_at = timezone.now()
        self.staff.profile.save(update_fields=["email_verified", "email_verified_at", "updated_at"])

    def tearDown(self):
        cache.clear()
        super().tearDown()

    # -------------------------------------------------------------------------
    # 1. ROLE DETECTION TESTS
    # -------------------------------------------------------------------------

    def test_superuser_effective_role_is_admin(self):
        """Superuser must be recognized as ADMIN even if profile was missing or corrupted."""
        self.client.force_authenticate(user=self.admin)
        res = self.client.get("/api/accounts/me/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["role"], "ADMIN")

    def test_staff_user_effective_role_is_admin(self):
        """Staff user must be recognized as ADMIN."""
        self.client.force_authenticate(user=self.staff)
        res = self.client.get("/api/accounts/me/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["role"], "ADMIN")

    def test_standard_user_role_is_user(self):
        """Standard user role must be USER."""
        self.client.force_authenticate(user=self.user)
        res = self.client.get("/api/accounts/me/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["role"], "USER")

    def test_profile_patch_updates_allowed_fields_for_user_and_admin(self):
        for account in (self.user, self.admin):
            self.client.force_authenticate(user=account)
            response = self.client.patch("/api/accounts/me/", {
                "organization": "ABC & Associates",
                "phone": "+919876543210",
            }, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            profile = UserProfile.objects.get(user=account)
            self.assertEqual(profile.organization, "ABC & Associates")
            self.assertEqual(profile.phone, "+919876543210")
            self.assertEqual(response.data["role"], "ADMIN" if account.is_staff or account.is_superuser else "USER")

    def test_profile_patch_rejects_invalid_organization_and_indian_phone(self):
        self.client.force_authenticate(user=self.user)
        invalid_org = self.client.patch("/api/accounts/me/", {"organization": "12345"}, format="json")
        self.assertEqual(invalid_org.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("organization", invalid_org.data)
        invalid_phone = self.client.patch("/api/accounts/me/", {"phone": "+91987654321"}, format="json")
        self.assertEqual(invalid_phone.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone", invalid_phone.data)

    def test_missing_profile_handling_for_admin(self):
        """If an admin's profile is deleted, fetching /me/ recreates it with ADMIN role."""
        UserProfile.objects.filter(user=self.admin).delete()
        self.assertFalse(UserProfile.objects.filter(user=self.admin).exists())

        self.client.force_authenticate(user=self.admin)
        res = self.client.get("/api/accounts/me/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["role"], "ADMIN")

        profile = UserProfile.objects.get(user=self.admin)
        self.assertEqual(profile.role, "ADMIN")

    def test_inconsistent_profile_role_repair(self):
        """If a superuser had role='USER' in database, it is automatically corrected to ADMIN."""
        profile, _ = UserProfile.objects.get_or_create(user=self.admin)
        # Forcibly update database to simulate inconsistent data
        UserProfile.objects.filter(id=profile.id).update(role="USER")

        self.client.force_authenticate(user=self.admin)
        res = self.client.get("/api/accounts/me/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["role"], "ADMIN")

    def test_unauthorized_user_cannot_access_admin_api(self):
        """Standard users must be forbidden from accessing admin endpoints."""
        self.client.force_authenticate(user=self.user)
        res = self.client.get("/api/accounts/admin/users/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_access_admin_api(self):
        """Admin users must be granted access to admin endpoints."""
        self.client.force_authenticate(user=self.admin)
        res = self.client.get("/api/accounts/admin/users/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    # -------------------------------------------------------------------------
    # 2. LOGIN AND REGISTRATION TESTS
    # -------------------------------------------------------------------------

    def test_login_valid_credentials_without_mfa_requires_enrollment(self):
        """Standard password login credentials without MFA must prompt for MFA setup enrollment without issuing tokens."""
        with patch("apps.accounts.views.send_email_verification_otp_email") as send_verification:
            res = self.client.post("/api/accounts/login/", {
                "username": "normaluser",
                "password": "Password@123",
            })
        send_verification.assert_not_called()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data.get("mfa_required"))
        self.assertTrue(res.data.get("mfa_setup_required"))
        self.assertIn("challenge", res.data)
        self.assertIn("qr_code", res.data)
        self.assertIn("secret", res.data)
        self.assertNotIn("access", res.data)
        self.assertNotIn("refresh", res.data)

    def test_login_with_email_address_succeeds_and_prompts_mfa(self):
        """Login with email address instead of username succeeds and prompts for MFA."""
        res = self.client.post("/api/accounts/login/", {
            "username": "superadmin@example.com",
            "password": "AdminPassword@123",
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data.get("mfa_required"))
        self.assertIn("challenge", res.data)
        self.assertNotIn("access", res.data)

    def test_login_with_mfa_enabled_requires_otp_challenge(self):
        """When user has MFA enabled, login prompts for 6-digit challenge without issuing tokens."""
        secret = pyotp.random_base32()
        profile = self.user.profile
        profile.totp_secret = secret
        profile.mfa_enabled = True
        profile.save()

        res = self.client.post("/api/accounts/login/", {
            "username": "normaluser",
            "password": "Password@123",
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["mfa_required"])
        self.assertIn("challenge", res.data)
        self.assertNotIn("access", res.data)
        self.assertNotIn("refresh", res.data)

    def test_login_invalid_credentials_rejected(self):
        """Invalid password returns 401."""
        res = self.client.post("/api/accounts/login/", {
            "username": "normaluser",
            "password": "WrongPassword",
        })
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_rejects_missing_or_invalid_access_token(self):
        response = self.client.get("/api/accounts/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid-access-token")
        response = self.client.get("/api/accounts/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_returns_access_token_for_existing_user(self):
        refresh = RefreshToken.for_user(self.user)
        response = self.client.post("/api/accounts/token/refresh/", {"refresh": str(refresh)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get("access"))

    def test_refresh_for_deleted_user_returns_controlled_unauthorized(self):
        refresh = str(RefreshToken.for_user(self.user))
        self.user.delete()

        response = self.client.post("/api/accounts/token/refresh/", {"refresh": refresh}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["detail"], "Session expired. Please log in again.")

    def test_unverified_user_cannot_login_or_refresh_or_access_protected_api(self):
        user = User.objects.create_user(
            username="unverified-access@example.com",
            email="unverified-access@example.com",
            password="Password@123",
        )
        user.profile.email_verified = False
        user.profile.email_verified_at = None
        user.profile.save(update_fields=["email_verified", "email_verified_at", "updated_at"])

        login = self.client.post("/api/accounts/login/", {
            "username": user.email,
            "password": "Password@123",
        })
        self.assertEqual(login.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(login.data["email_verification_required"])

        refresh = RefreshToken.for_user(user)
        me = self.client.get(
            "/api/accounts/me/",
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
        )
        self.assertEqual(me.status_code, status.HTTP_401_UNAUTHORIZED)

        refresh_response = self.client.post(
            "/api/accounts/token/refresh/", {"refresh": str(refresh)}, format="json"
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    @patch("apps.accounts.views.send_email_verification_otp_email", return_value=True)
    def test_unverified_user_without_certificate_can_resend_verification(self, send_email):
        user = User.objects.create_user(
            username="resend-no-cert@example.com",
            email="resend-no-cert@example.com",
            password="Password@123",
        )
        response = self.client.post(
            "/api/accounts/resend-verification/", {"email": user.email}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        send_email.assert_called_once()
        self.assertTrue(
            EmailVerificationToken.objects.filter(user=user, is_used=False).exists()
        )

    def test_refresh_rejects_invalid_and_expired_tokens(self):
        invalid = self.client.post("/api/accounts/token/refresh/", {"refresh": "not-a-jwt"}, format="json")
        self.assertEqual(invalid.status_code, status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(self.user)
        refresh.set_exp(lifetime=timedelta(seconds=-1))
        expired = self.client.post(
            "/api/accounts/token/refresh/",
            {"refresh": str(refresh)},
            format="json",
        )
        self.assertEqual(expired.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_registration_creates_user_with_user_role(self):
        """Every registration sends verification, even when no certificate exists."""
        mail.outbox = []
        with patch("apps.certificates.emails.send_certificate_issued_email") as certificate_email:
            res = self.client.post("/api/accounts/register/", {
                "username": "newbie",
                "email": "newbie@example.com",
                "first_name": "New",
                "last_name": "Bie",
                "password": "NewPassword@123",
                "password_confirm": "NewPassword@123",
            })
        self.assertEqual(res.status_code, status.HTTP_202_ACCEPTED)
        certificate_email.assert_not_called()
        self.assertNotIn("verification_email_sent", res.data)
        self.assertIn("If registration can be completed", res.data["detail"])
        self.assertTrue(EmailVerificationToken.objects.filter(user__username="newbie", is_used=False).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["newbie@example.com"])
        self.assertIn("Verify Your Email Address", mail.outbox[0].subject)
        otp_match = re.search(r"\b(\d{6})\b", mail.outbox[0].body)
        self.assertIsNotNone(otp_match)
        verification = self.client.post("/api/accounts/verify-email/", {
            "email": "newbie@example.com", "otp": otp_match.group(1),
        })
        self.assertEqual(verification.status_code, status.HTTP_200_OK)
        self.assertTrue(verification.data["email_verified"])
        new_user = User.objects.get(username="newbie")
        self.assertFalse(new_user.is_staff)
        self.assertFalse(new_user.is_superuser)
        self.assertEqual(new_user.profile.role, "USER")

        login = self.client.post("/api/accounts/login/", {
            "username": "newbie@example.com",
            "password": "NewPassword@123",
        })
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertTrue(login.data.get("mfa_required"))

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_registration_verification_email_is_independent_of_existing_certificate(self):
        """Verification email is sent independently of a pre-existing certificate."""
        mail.outbox = []
        Certificate.objects.create(
            owner=None,
            recipient_email="claimed-later@example.com",
            title="Existing credential",
            issuer="OneSmarter",
            certificate_number="OSCV-2026-REGEMAIL01",
            recipient_name="New User",
            issue_date=timezone.now().date(),
            status=Certificate.Status.VERIFIED,
        )

        response = self.client.post("/api/accounts/register/", {
            "username": "claimed-later@example.com",
            "email": "claimed-later@example.com",
            "first_name": "New",
            "last_name": "User",
            "password": "NewPassword@123",
            "password_confirm": "NewPassword@123",
        })

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertNotIn("verification_email_sent", response.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["claimed-later@example.com"])
        self.assertIn("Verify Your Email Address", mail.outbox[0].subject)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_registration_delivery_failure_is_reported_and_resend_can_retry_immediately(self):
        mail.outbox = []
        Certificate.objects.create(
            owner=None,
            recipient_email="retry-verification@example.com",
            title="Issued credential",
            issuer="OneSmarter",
            certificate_number="OSCV-2026-REGRETRY01",
            recipient_name="Retry User",
            issue_date=timezone.now().date(),
            status=Certificate.Status.VERIFIED,
        )
        with patch(
            "apps.accounts.views.send_email_verification_otp_email",
            side_effect=RuntimeError("mock SMTP failure"),
        ):
            response = self.client.post("/api/accounts/register/", {
                "username": "retry-verification@example.com",
                "email": "retry-verification@example.com",
                "first_name": "Retry",
                "last_name": "User",
                "password": "NewPassword@123",
                "password_confirm": "NewPassword@123",
            })

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertNotIn("verification_email_sent", response.data)
        failed_token = EmailVerificationToken.objects.get(user__email="retry-verification@example.com")
        self.assertTrue(failed_token.is_used)

        with patch(
            "apps.accounts.views.send_email_verification_otp_email",
            return_value=True,
        ) as resend:
            retry_response = self.client.post("/api/accounts/resend-verification/", {
                "email": "retry-verification@example.com",
            })

        self.assertEqual(retry_response.status_code, status.HTTP_200_OK)
        resend.assert_called_once()
        self.assertTrue(
            EmailVerificationToken.objects.filter(
                user__email="retry-verification@example.com", is_used=False
            ).exists()
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_email_verification_otp_expires_and_locks_after_five_failures(self):
        Certificate.objects.create(
            owner=None,
            recipient_email="otp-lock@example.com",
            title="Issued credential",
            issuer="OneSmarter",
            certificate_number="OSCV-2026-OTPLOCK01",
            recipient_name="OTP Lock",
            issue_date=timezone.now().date(),
            status=Certificate.Status.VERIFIED,
        )
        response = self.client.post("/api/accounts/register/", {
            "username": "otp-lock@example.com",
            "email": "otp-lock@example.com",
            "first_name": "OTP",
            "last_name": "Lock",
            "password": "NewPassword@123",
            "password_confirm": "NewPassword@123",
        })
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        token = EmailVerificationToken.objects.get(user__email="otp-lock@example.com")
        token.otp_hash = hashlib.sha256(b"111111").hexdigest()
        token.save(update_fields=["otp_hash"])
        self.assertLessEqual(token.expires_at - timezone.now(), timedelta(minutes=10))
        for _ in range(5):
            failed = self.client.post("/api/accounts/verify-email/", {
                "email": "otp-lock@example.com", "otp": "000000",
            })
            self.assertEqual(failed.status_code, status.HTTP_400_BAD_REQUEST)
        token.refresh_from_db()
        self.assertEqual(token.attempts, 5)
        self.assertTrue(token.is_used)

    def test_email_verification_expired_otp_cannot_be_used(self):
        user = User.objects.create_user(
            username="expired-otp@example.com",
            email="expired-otp@example.com",
            password="Password@123",
        )
        user.profile.email_verified = False
        user.profile.save()
        token = EmailVerificationToken.objects.create(
            user=user,
            token_hash=hashlib.sha256(b"link").hexdigest(),
            otp_hash=hashlib.sha256(b"123456").hexdigest(),
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        response = self.client.post("/api/accounts/verify-email/", {
            "email": user.email, "otp": "123456",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        user.profile.refresh_from_db()
        self.assertFalse(user.profile.email_verified)
        token.refresh_from_db()
        self.assertTrue(token.is_used)

    def test_duplicate_email_registration_rejected(self):
        """Registration with an already registered email must be rejected."""
        res = self.client.post("/api/accounts/register/", {
            "username": "duplicate_attempt",
            "email": "normaluser@example.com",
            "first_name": "Dup",
            "last_name": "Licat",
            "password": "Password@123",
            "password_confirm": "Password@123",
        })
        self.assertEqual(res.status_code, status.HTTP_202_ACCEPTED)
        self.assertNotIn("email", res.data)
        self.assertNotIn("verification_email_sent", res.data)
        self.assertIn("If registration can be completed", res.data["detail"])

    # -------------------------------------------------------------------------
    # 3. MFA SETUP, VERIFICATION, AND REPLAY TESTS
    # -------------------------------------------------------------------------

    def test_mfa_setup_and_confirm_flow(self):
        """Authenticated user sets up MFA: generates secret/QR -> confirms valid code -> enabled."""
        self.client.force_authenticate(user=self.user)
        setup_res = self.client.post("/api/accounts/mfa/setup/")
        self.assertEqual(setup_res.status_code, status.HTTP_200_OK)
        self.assertIn("qr_code", setup_res.data)
        secret = setup_res.data["secret"]

        # Confirm with valid TOTP code
        code = pyotp.TOTP(secret).now()
        mail.outbox = []
        with self.captureOnCommitCallbacks(execute=True):
            confirm_res = self.client.post("/api/accounts/mfa/confirm/", {"code": code})
        self.assertEqual(confirm_res.status_code, status.HTTP_200_OK)

        profile = UserProfile.objects.get(user=self.user)
        self.assertTrue(profile.mfa_enabled)
        self.assertEqual(profile.totp_secret, secret)
        self.assertEqual(len(mail.outbox), 1)
        from apps.audit.models import AuditLog
        self.assertTrue(AuditLog.objects.filter(actor=self.user, action=AuditLog.Action.MFA_ENABLED).exists())

    def test_mfa_invalid_otp_rejected(self):
        """Submitting an invalid OTP must be rejected with 401."""
        secret = pyotp.random_base32()
        profile = self.user.profile
        profile.totp_secret = secret
        profile.mfa_enabled = True
        profile.save()

        login_res = self.client.post("/api/accounts/login/", {
            "username": "normaluser",
            "password": "Password@123",
        })
        challenge = login_res.data["challenge"]

        res = self.client.post("/api/accounts/login/", {
            "challenge": challenge,
            "code": "000000",
        })
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_subsequent_login_requires_existing_mfa(self):
        """Once enrolled, subsequent login prompts for 6-digit code without re-generating secret."""
        # Setup MFA
        secret = pyotp.random_base32()
        profile = self.user.profile
        profile.totp_secret = secret
        profile.mfa_enabled = True
        profile.save()

        login_res = self.client.post("/api/accounts/login/", {
            "username": "normaluser",
            "password": "Password@123",
        })
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        self.assertTrue(login_res.data["mfa_required"])
        self.assertFalse(login_res.data["mfa_setup_required"])
        self.assertNotIn("secret", login_res.data)

        challenge = login_res.data["challenge"]
        code = pyotp.TOTP(secret).now()

        verify_res = self.client.post("/api/accounts/login/", {
            "challenge": challenge,
            "code": code,
        })
        self.assertEqual(verify_res.status_code, status.HTTP_200_OK)
        self.assertIn("access", verify_res.data)

    def test_replayed_otp_rejected(self):
        """The same OTP cannot be reused within its valid window."""
        secret = pyotp.random_base32()
        profile = self.user.profile
        profile.totp_secret = secret
        profile.mfa_enabled = True
        profile.save()

        # First login challenge
        login_res1 = self.client.post("/api/accounts/login/", {
            "username": "normaluser",
            "password": "Password@123",
        })
        challenge1 = login_res1.data["challenge"]
        code = pyotp.TOTP(secret).now()

        # Succeeded once
        res1 = self.client.post("/api/accounts/login/", {
            "challenge": challenge1,
            "code": code,
        })
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        # Second login attempt with same code immediately
        login_res2 = self.client.post("/api/accounts/login/", {
            "username": "normaluser",
            "password": "Password@123",
        })
        challenge2 = login_res2.data["challenge"]

        res2 = self.client.post("/api/accounts/login/", {
            "challenge": challenge2,
            "code": code,
        })
        self.assertEqual(res2.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("already been used", res2.data["detail"].lower())

    # -------------------------------------------------------------------------
    # 4. MFA RECOVERY TESTS
    # -------------------------------------------------------------------------

    def test_mfa_recovery_request_valid_and_invalid_email(self):
        """Recovery request returns generic 200 message regardless of whether email exists."""
        mail.outbox = []

        # Enrolled user request
        self.user.profile.mfa_enabled = True
        self.user.profile.totp_secret = pyotp.random_base32()
        self.user.profile.save()

        res1 = self.client.post("/api/accounts/mfa/recovery/request/", {
            "email": "normaluser@example.com",
        })
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertIn("If an account with that email", res1.data["detail"])
        self.assertEqual(len(mail.outbox), 1)

        # Non-existent user request
        res2 = self.client.post("/api/accounts/mfa/recovery/request/", {
            "email": "nobody@example.com",
        })
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertIn("If an account with that email", res2.data["detail"])
        # No extra email sent
        self.assertEqual(len(mail.outbox), 1)

    def test_full_mfa_recovery_and_re_enrollment_workflow(self):
        """Full recovery: request -> confirm with link -> re-enroll new authenticator -> JWT issued."""
        mail.outbox = []
        old_secret = pyotp.random_base32()
        profile = self.admin.profile
        profile.mfa_enabled = True
        profile.totp_secret = old_secret
        profile.save()

        # Step 1: Request recovery
        req_res = self.client.post("/api/accounts/mfa/recovery/request/", {
            "email": "superadmin@example.com",
        })
        self.assertEqual(req_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

        # Extract token from database record
        token_record = MFARecoveryToken.objects.filter(user=self.admin, is_used=False).first()
        self.assertIsNotNone(token_record)

        # In email, token is in plaintext; recreate matching token
        raw_token = "test_recovery_token_12345"
        token_record.token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        token_record.save()

        # Step 2: Open link (confirm)
        confirm_res = self.client.post("/api/accounts/mfa/recovery/confirm/", {
            "token": raw_token,
        })
        self.assertEqual(confirm_res.status_code, status.HTTP_200_OK)
        self.assertIn("qr_code", confirm_res.data)
        self.assertIn("challenge", confirm_res.data)
        new_secret = confirm_res.data["secret"]
        challenge = confirm_res.data["challenge"]

        missing_payload = self.client.post("/api/accounts/mfa/recovery/complete/", {})
        self.assertEqual(missing_payload.status_code, status.HTTP_400_BAD_REQUEST)
        invalid_code = self.client.post("/api/accounts/mfa/recovery/complete/", {
            "challenge": challenge,
            "code": "not-a-code",
        })
        self.assertEqual(invalid_code.status_code, status.HTTP_400_BAD_REQUEST)

        # Step 3: Complete recovery with valid OTP
        new_otp = pyotp.TOTP(new_secret).now()
        complete_res = self.client.post("/api/accounts/mfa/recovery/complete/", {
            "challenge": challenge,
            "code": new_otp,
        })
        self.assertEqual(complete_res.status_code, status.HTTP_200_OK)
        self.assertIn("access", complete_res.data)

        # Token is now used
        token_record.refresh_from_db()
        self.assertTrue(token_record.is_used)

        # Admin role is preserved
        self.admin.profile.refresh_from_db()
        self.assertEqual(self.admin.profile.role, "ADMIN")
        self.assertEqual(self.admin.profile.totp_secret, new_secret)
        self.assertNotEqual(self.admin.profile.totp_secret, old_secret)

        replay = self.client.post("/api/accounts/mfa/recovery/complete/", {
            "challenge": challenge,
            "code": new_otp,
        })
        self.assertEqual(replay.status_code, status.HTTP_400_BAD_REQUEST)

    def test_expired_recovery_token_rejected(self):
        """Expired recovery token must be rejected."""
        raw_token = "expired_token_123"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        MFARecoveryToken.objects.create(
            user=self.user,
            token_hash=token_hash,
            expires_at=timezone.now() - timedelta(minutes=5),
        )

        res = self.client.post("/api/accounts/mfa/recovery/confirm/", {
            "token": raw_token,
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expired", res.data["detail"].lower())

    def test_reused_recovery_token_rejected(self):
        """Used recovery token cannot be reused."""
        raw_token = "already_used_token"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        MFARecoveryToken.objects.create(
            user=self.user,
            token_hash=token_hash,
            expires_at=timezone.now() + timedelta(minutes=10),
            is_used=True,
            used_at=timezone.now(),
        )

        res = self.client.post("/api/accounts/mfa/recovery/confirm/", {
            "token": raw_token,
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # -------------------------------------------------------------------------
    # 5. DATA PRESERVATION TESTS
    # -------------------------------------------------------------------------

    def test_certificate_and_user_preservation(self):
        """Verify user and certificate relationship preservation."""
        cert = Certificate.objects.create(
            owner=self.user,
            title="Test Certificate",
            issuer="Cert Authority",
            certificate_number="CERT-TEST-999",
            recipient_name="Normal User",
            issue_date=timezone.now().date(),
        )

        # Re-authenticate and verify certificate ownership
        self.assertEqual(cert.owner_id, self.user.id)
        self.assertEqual(self.user.certificates.count(), 1)
        self.assertEqual(self.admin.profile.role, "ADMIN")
        self.assertEqual(self.user.profile.role, "USER")

    # -------------------------------------------------------------------------
    # 6. PASSWORD RESET WORKFLOW TESTS
    # -------------------------------------------------------------------------

    def test_password_reset_request_valid_and_unknown_email(self):
        """Reset request returns generic message and sends reset email only for existing user."""
        mail.outbox = []

        # Known user request
        res1 = self.client.post("/api/accounts/password-reset/request/", {
            "email": "normaluser@example.com",
        })
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertIn("reset", res1.data["detail"].lower())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Reset Your OneSmarter-CertiVerify Password", mail.outbox[0].subject)
        self.assertIn("/reset-password#token=", mail.outbox[0].body)

        # Unknown email request (clear cache cooldown first for testing)
        cache.clear()
        res2 = self.client.post("/api/accounts/password-reset/request/", {
            "email": "unknown@example.com",
        })
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertIn("reset", res2.data["detail"].lower())
        # No extra email sent
        self.assertEqual(len(mail.outbox), 1)

    def test_password_reset_cooldown_is_generic(self):
        first = self.client.post("/api/accounts/password-reset/request/", {"email": "normaluser@example.com"})
        second = self.client.post("/api/accounts/password-reset/request/", {"email": "normaluser@example.com"})
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["detail"], second.data["detail"])

    def test_full_password_reset_link_workflow_and_session_revocation(self):
        mail.outbox = []
        user = self.user
        user.profile.mfa_enabled = True
        user.profile.totp_secret = pyotp.random_base32()
        user.profile.save()
        from apps.accounts.authentication import issue_user_refresh_token
        old_access = str(issue_user_refresh_token(user).access_token)

        request = self.client.post("/api/accounts/password-reset/request/", {
            "email": user.email,
        })
        self.assertEqual(request.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        match = re.search(r"/reset-password#token=([^\s\"<&]+)", mail.outbox[0].body)
        self.assertIsNotNone(match)
        raw_token = match.group(1)
        self.assertTrue(PasswordResetToken.objects.filter(
            user=user, token_hash=hashlib.sha256(raw_token.encode()).hexdigest(), is_used=False
        ).exists())
        self.assertFalse(PasswordResetRequest.objects.filter(user=user, is_completed=False).exists())

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {old_access}")
        new_password = "BrandNewStrongPassword@2026"
        completed = self.client.post("/api/accounts/password-reset/complete/", {
            "token": raw_token,
            "password": new_password,
            "password_confirm": new_password,
        })
        self.assertEqual(completed.status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get("/api/accounts/me/").status_code, status.HTTP_401_UNAUTHORIZED)
        self.client.credentials()

        replay = self.client.post("/api/accounts/password-reset/complete/", {
            "token": raw_token,
            "password": new_password,
            "password_confirm": new_password,
        })
        self.assertEqual(replay.status_code, status.HTTP_400_BAD_REQUEST)
        user.refresh_from_db()
        self.assertTrue(user.check_password(new_password))
        user.profile.refresh_from_db()
        self.assertTrue(user.profile.mfa_enabled)

    def test_password_reset_otp_endpoint_is_removed(self):
        response = self.client.post("/api/accounts/password-reset/verify/", {
            "email": self.user.email,
            "otp": "000000",
        })
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(self.user.check_password("Password@123"))

    def test_password_reset_expired_link_is_rejected(self):
        raw_token = "expired-reset-link-token"
        PasswordResetToken.objects.create(
            user=self.user,
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        response = self.client.post("/api/accounts/password-reset/complete/", {
            "token": raw_token,
            "password": "ValidNewPassword@123",
            "password_confirm": "ValidNewPassword@123",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(self.user.check_password("Password@123"))

    def test_password_reset_mismatched_and_weak_passwords_rejected(self):
        raw_token = "valid-reset-link-token"
        PasswordResetToken.objects.create(
            user=self.user,
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        mismatch = self.client.post("/api/accounts/password-reset/complete/", {
            "token": raw_token,
            "password": "Password1@Strong",
            "password_confirm": "DifferentPassword2@Strong",
        })
        self.assertEqual(mismatch.status_code, status.HTTP_400_BAD_REQUEST)
        weak = self.client.post("/api/accounts/password-reset/complete/", {
            "token": raw_token,
            "password": "123",
            "password_confirm": "123",
        })
        self.assertEqual(weak.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", weak.data)

    def test_admin_password_reset_preserves_admin_role_and_mfa(self):
        mail.outbox = []
        admin = self.admin
        admin.profile.mfa_enabled = True
        admin.profile.totp_secret = pyotp.random_base32()
        admin.profile.save()
        self.client.post("/api/accounts/password-reset/request/", {"email": admin.email})
        self.assertEqual(len(mail.outbox), 1)
        match = re.search(r"/reset-password#token=([^\s\"<&]+)", mail.outbox[0].body)
        self.assertIsNotNone(match)
        new_pass = "SuperAdminNewPass@999"
        response = self.client.post("/api/accounts/password-reset/complete/", {
            "token": match.group(1),
            "password": new_pass,
            "password_confirm": new_pass,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        admin.refresh_from_db()
        admin.profile.refresh_from_db()
        self.assertTrue(admin.is_superuser)
        self.assertEqual(admin.profile.role, "ADMIN")
        self.assertTrue(admin.profile.mfa_enabled)

    def test_mfa_recovery_email_contains_configured_frontend_url(self):
        """Recovery email must contain FRONTEND_URL and a secure token."""
        mail.outbox = []
        res = self.client.post("/api/accounts/mfa/recovery/request/", {
            "email": "normaluser@example.com",
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        email_body = mail.outbox[0].body
        self.assertIn("/mfa-recovery?token=", email_body)
        self.assertIn("15 minutes", email_body)

    @skipUnless(connection.vendor == "postgresql", "normalized email index is PostgreSQL-specific")
    def test_database_prevents_duplicate_normalized_email_accounts(self):
        """The database constraint closes the registration email race."""
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(
                    username="second_dup_user",
                    email=" NORMALUSER@example.com ",
                    password="OtherPassword@123",
                )
        self.assertEqual(User.objects.filter(email__iexact="normaluser@example.com").count(), 1)

    def test_password_reset_via_email_link_end_to_end(self):
        """
        Complete link-based password reset workflow:
        1. Request reset -> creates token, sends branded email with link.
        2. Validate token endpoint confirms token validity.
        3. Complete reset updates password in PostgreSQL, marks token used, sends confirmation email.
        4. Old password fails, new password succeeds and preserves MFA.
        5. Token replay rejected.
        """
        mail.outbox = []
        user = self.user
        user.profile.mfa_enabled = True
        user.profile.totp_secret = pyotp.random_base32()
        user.profile.save()

        # Step 1: Request reset
        cache.clear()
        req_res = self.client.post("/api/accounts/password-reset/request/", {
            "email": "normaluser@example.com",
        })
        self.assertEqual(req_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Reset Your OneSmarter-CertiVerify Password", mail.outbox[0].subject)
        self.assertIn("/reset-password#token=", mail.outbox[0].body)

        # Retrieve token from database
        token_record = PasswordResetToken.objects.filter(user=user, is_used=False).first()
        self.assertIsNotNone(token_record)

        # In a real email, the token parameter matches the raw urlsafe token.
        # Create a deterministic raw token for validation testing:
        import secrets
        raw_token = secrets.token_urlsafe(32)
        token_record.token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        token_record.save()

        # Step 2: Validate token endpoint
        val_res = self.client.post("/api/accounts/password-reset/validate/", {
            "token": raw_token,
        })
        self.assertEqual(val_res.status_code, status.HTTP_200_OK)
        self.assertTrue(val_res.data["valid"])

        # Also test GET method on validate endpoint
        val_get_res = self.client.get(f"/api/accounts/password-reset/validate/?token={raw_token}")
        self.assertEqual(val_get_res.status_code, status.HTTP_200_OK)
        self.assertTrue(val_get_res.data["valid"])

        # Step 3: Complete password reset
        new_password = "SecureNewPassword#2026"
        comp_res = self.client.post("/api/accounts/password-reset/complete/", {
            "token": raw_token,
            "password": new_password,
            "password_confirm": new_password,
        })
        self.assertEqual(comp_res.status_code, status.HTTP_200_OK)
        self.assertIn("changed successfully", comp_res.data["detail"].lower())

        # Check confirmation notification email was sent
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("Password Has Been Changed", mail.outbox[1].subject)

        # Token is marked used
        token_record.refresh_from_db()
        self.assertTrue(token_record.is_used)

        # Replay attempt is rejected
        replay_res = self.client.post("/api/accounts/password-reset/complete/", {
            "token": raw_token,
            "password": "AnotherPassword#2026",
            "password_confirm": "AnotherPassword#2026",
        })
        self.assertEqual(replay_res.status_code, status.HTTP_400_BAD_REQUEST)

        # Validate endpoint also rejects consumed token
        val_consumed = self.client.post("/api/accounts/password-reset/validate/", {
            "token": raw_token,
        })
        self.assertEqual(val_consumed.status_code, status.HTTP_400_BAD_REQUEST)

        # Old password rejected
        old_login = self.client.post("/api/accounts/login/", {
            "username": "normaluser@example.com",
            "password": "Password@123",
        })
        self.assertEqual(old_login.status_code, status.HTTP_401_UNAUTHORIZED)

        # New password works and still requires MFA
        new_login = self.client.post("/api/accounts/login/", {
            "username": "normaluser@example.com",
            "password": new_password,
        })
        self.assertEqual(new_login.status_code, status.HTTP_200_OK)
        self.assertTrue(new_login.data["mfa_required"])
        user.profile.refresh_from_db()
        self.assertTrue(user.profile.mfa_enabled)

    def test_mfa_recovery_link_workflow_end_to_end(self):
        """
        Complete MFA reauthorization/recovery workflow:
        1. Request recovery -> creates recovery token, sends email with link.
        2. Recovery confirm -> returns new QR code and challenge token.
        3. Recovery complete -> verifies OTP, activates new secret, sends confirmation email.
        4. User is NOT automatically logged in (requires manual login with new authenticator).
        5. Token replay is rejected.
        """
        mail.outbox = []
        user = self.user
        user.profile.mfa_enabled = True
        old_secret = pyotp.random_base32()
        user.profile.totp_secret = old_secret
        user.profile.save()

        # Step 1: Request recovery
        cache.clear()
        req_res = self.client.post("/api/accounts/mfa/recovery/request/", {
            "email": "normaluser@example.com",
        })
        self.assertEqual(req_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("MFA Reauthorization Request", mail.outbox[0].subject)
        self.assertIn("/mfa-recovery?token=", mail.outbox[0].body)

        # Retrieve token record and set test raw token
        import secrets
        raw_token = secrets.token_urlsafe(32)
        rec_token = MFARecoveryToken.objects.filter(user=user, is_used=False).first()
        self.assertIsNotNone(rec_token)
        rec_token.token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        rec_token.save()

        # Step 2: Validate token and get QR code / challenge
        confirm_res = self.client.post("/api/accounts/mfa/recovery/confirm/", {
            "token": raw_token,
        })
        self.assertEqual(confirm_res.status_code, status.HTTP_200_OK)
        self.assertIn("qr_code", confirm_res.data)
        self.assertIn("challenge", confirm_res.data)
        self.assertIn("secret", confirm_res.data)
        challenge = confirm_res.data["challenge"]
        new_secret = confirm_res.data["secret"]

        # Ensure pending secret is set, but active secret is NOT updated yet
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.pending_totp_secret, new_secret)
        self.assertEqual(user.profile.totp_secret, old_secret)

        # Step 3: Complete recovery with valid OTP from new secret
        totp = pyotp.TOTP(new_secret)
        valid_code = totp.now()

        with self.captureOnCommitCallbacks(execute=True):
            complete_res = self.client.post("/api/accounts/mfa/recovery/complete/", {
                "challenge": challenge,
                "code": valid_code,
            })
        self.assertEqual(complete_res.status_code, status.HTTP_200_OK)
        self.assertTrue(complete_res.data.get("success"))
        self.assertIn("recovery complete", complete_res.data.get("detail", "").lower())

        # Verify new secret is now active
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.totp_secret, new_secret)
        self.assertEqual(user.profile.pending_totp_secret, "")
        self.assertTrue(user.profile.mfa_enabled)

        # Verify confirmation email sent
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("Two-Factor Authentication Updated", mail.outbox[1].subject)

        # Step 4: Replay rejected
        rec_token.refresh_from_db()
        self.assertTrue(rec_token.is_used)
        replay_confirm = self.client.post("/api/accounts/mfa/recovery/confirm/", {
            "token": raw_token,
        })
        self.assertEqual(replay_confirm.status_code, status.HTTP_400_BAD_REQUEST)

    # -------------------------------------------------------------------------
    # 6. GOOGLE AUTHENTICATION AND SET MANUAL PASSWORD TESTS
    # -------------------------------------------------------------------------

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="test-google-client-id")
    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_login_new_user_success_without_mfa(self, mock_verify):
        """New Google user authenticates and receives JWT tokens directly without TOTP challenge."""
        mock_verify.return_value = {
            "iss": "https://accounts.google.com",
            "sub": "google-sub-12345",
            "email": "googleuser@example.com",
            "email_verified": True,
            "given_name": "Google",
            "family_name": "User",
        }
        res = self.client.post("/api/accounts/google-login/", {
            "id_token": "valid-simulated-token",
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data.get("mfa_required"))
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)
        self.assertTrue(res.data["user"]["email_verified"])
        self.assertFalse(res.data["user"]["has_usable_password"])
        self.assertTrue(res.data["user"]["is_google_user"])

        # Check DB state
        user = User.objects.get(email="googleuser@example.com")
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.profile.email_verified)
        self.assertEqual(user.profile.google_sub, "google-sub-12345")
        self.assertEqual(mock_verify.call_args.kwargs["audience"], "test-google-client-id")

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="test-google-client-id")
    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_login_existing_user_linked(self, mock_verify):
        """Existing user already linked by google_sub logs in directly."""
        google_user = User.objects.create_user(
            username="existing_google",
            email="existing_google@example.com",
        )
        google_user.set_unusable_password()
        google_user.save()
        google_user.profile.google_sub = "google-sub-existing"
        google_user.profile.email_verified = True
        google_user.profile.save()

        mock_verify.return_value = {
            "iss": "https://accounts.google.com",
            "sub": "google-sub-existing",
            "email": "existing_google@example.com",
            "email_verified": True,
        }
        res = self.client.post("/api/accounts/google-login/", {
            "id_token": "valid-simulated-token",
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["user"]["username"], "existing_google")

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="test-google-client-id")
    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_login_rejects_inactive_linked_account(self, mock_verify):
        user = User.objects.create_user(
            username="inactive_google",
            email="inactive_google@example.com",
            is_active=False,
        )
        user.profile.google_sub = "google-sub-inactive"
        user.profile.email_verified = True
        user.profile.save()
        mock_verify.return_value = {
            "iss": "https://accounts.google.com",
            "sub": "google-sub-inactive",
            "email": "inactive_google@example.com",
            "email_verified": True,
        }

        response = self.client.post("/api/accounts/google-login/", {"id_token": "valid-token"})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", response.data)

    @skipUnless(connection.vendor == "postgresql", "identity constraints are verified on PostgreSQL")
    def test_database_rejects_duplicate_nonempty_google_subjects(self):
        from django.db import IntegrityError, transaction

        User.objects.create_user(
            username="normalized_email_first",
            email=" Duplicate.Email@example.com ",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(
                username="normalized_email_second",
                email="duplicate.email@example.com",
            )

        first = User.objects.create_user(username="google_sub_first", email="google-sub-first@example.com")
        second = User.objects.create_user(username="google_sub_second", email="google-sub-second@example.com")
        first.profile.google_sub = "google-sub-unique"
        first.profile.save(update_fields=["google_sub", "updated_at"])

        second.profile.google_sub = "google-sub-unique"
        with self.assertRaises(IntegrityError), transaction.atomic():
            second.profile.save(update_fields=["google_sub", "updated_at"])


    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.example.test",
        EMAIL_HOST_USER="sender@example.test",
        EMAIL_HOST_PASSWORD="test-password",
        EMAIL_USE_TLS=True,
        EMAIL_USE_SSL=False,
    )
    def test_smtp_preflight_reconnects_before_sending_once(self):
        import smtplib
        from types import SimpleNamespace
        from django.core.mail.backends.smtp import EmailBackend
        from apps.accounts.services.email_service import send_account_email

        connection = EmailBackend()
        first_protocol = Mock()
        first_protocol.noop.side_effect = smtplib.SMTPServerDisconnected("Server not connected")
        second_protocol = Mock()
        second_protocol.noop.return_value = (250, b"OK")
        open_calls = 0

        def open_connection():
            nonlocal open_calls
            open_calls += 1
            connection.connection = SimpleNamespace(
                close=Mock(),
                protocol=first_protocol if open_calls == 1 else second_protocol,
            )
            connection.connection.noop = connection.connection.protocol.noop
            return True

        with patch("apps.accounts.services.email_service.get_connection", return_value=connection), \
             patch.object(connection, "open", side_effect=open_connection), \
             patch.object(connection, "close", side_effect=lambda: setattr(connection, "connection", None)), \
             patch("apps.accounts.services.email_service.EmailMultiAlternatives.send", return_value=1) as send:
            self.assertTrue(send_account_email("recipient@example.test", "Subject", "Body"))

        self.assertEqual(open_calls, 2)
        send.assert_called_once_with(fail_silently=False)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_email_backend_failure_is_reported_without_claiming_success(self):
        from apps.accounts.services.email_service import EmailDeliveryError, send_account_email

        with patch("apps.accounts.services.email_service.EmailMultiAlternatives.send", side_effect=RuntimeError("mock transport error")):
            with self.assertRaises(EmailDeliveryError):
                send_account_email("recipient@example.com", "Test", "Body")

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="test-google-client-id")
    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_login_syncs_changed_verified_email_for_existing_identity(self, mock_verify):
        user = User.objects.create_user(
            username="google_email_change",
            email="old-google-email@example.com",
            password="Password@123",
        )
        user.profile.google_sub = "google-sub-email-change"
        user.profile.email_verified = True
        user.profile.save()
        mock_verify.return_value = {
            "iss": "https://accounts.google.com",
            "sub": "google-sub-email-change",
            "email": "new-google-email@example.com",
            "email_verified": True,
        }

        response = self.client.post("/api/accounts/google-login/", {"id_token": "valid-token"})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(response.data["mfa_required"])
        self.assertNotIn("access", response.data)
        user.refresh_from_db()
        self.assertEqual(user.email, "new-google-email@example.com")

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="test-google-client-id")
    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_login_does_not_link_inactive_password_account(self, mock_verify):
        user = User.objects.create_user(
            username="inactive_manual",
            email="inactive_manual@example.com",
            password="Password@123",
            is_active=False,
        )
        mock_verify.return_value = {
            "iss": "https://accounts.google.com",
            "sub": "google-sub-inactive-manual",
            "email": "inactive_manual@example.com",
            "email_verified": True,
        }

        response = self.client.post("/api/accounts/google-login/", {"id_token": "valid-token"})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        user.profile.refresh_from_db()
        self.assertFalse(user.profile.email_verified)
        self.assertFalse(user.profile.google_sub)

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="test-google-client-id")
    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_login_links_existing_verified_password_account_without_duplicate(self, mock_verify):
        """Verified manual account keeps its identity and data when linked to Google, including repeat login."""
        user = User.objects.create_user(
            username="verified_manual",
            email="Verified.Manual@example.com",
            password="Password@123",
        )
        user.profile.email_verified = True
        user.profile.save(update_fields=["email_verified", "updated_at"])
        certificate = Certificate.objects.create(
            owner=user,
            recipient_email=user.email,
            title="Existing course",
            issuer="OneSmarter",
            certificate_number="OSCV-2026-GOOGLELINK01",
            recipient_name="Verified Manual",
            issue_date=timezone.now().date(),
            status=Certificate.Status.VERIFIED,
        )
        original_user_id = user.pk
        original_profile_id = user.profile.pk
        mock_verify.return_value = {
            "iss": "https://accounts.google.com",
            "sub": "google-sub-manual-verified",
            "email": "verified.manual@example.com",
            "email_verified": True,
        }

        for _ in range(2):
            response = self.client.post("/api/accounts/google-login/", {"id_token": "verified-token"})
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
            self.assertTrue(response.data["mfa_required"])
            self.assertTrue(response.data["mfa_setup_required"])
            self.assertNotIn("access", response.data)
            self.assertNotIn("refresh", response.data)

        user.refresh_from_db()
        user.profile.refresh_from_db()
        certificate.refresh_from_db()
        self.assertEqual(User.objects.filter(email__iexact=user.email).count(), 1)
        self.assertTrue(user.has_usable_password())
        self.assertTrue(user.profile.email_verified)
        self.assertEqual(user.profile.google_sub, "google-sub-manual-verified")
        self.assertEqual(certificate.owner_id, original_user_id)
        self.assertEqual(mock_verify.call_args.kwargs["audience"], "test-google-client-id")

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="test-google-client-id")
    @patch("apps.accounts.views.send_email_verification_otp_email", return_value=True)
    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_verified_email_can_securely_link_unverified_no_certificate_registration(self, mock_verify, mock_verification_email):
        registration = self.client.post("/api/accounts/register/", {
            "username": "unverified.manual@example.com",
            "email": "unverified.manual@example.com",
            "first_name": "Unverified",
            "last_name": "Manual",
            "password": "Password@123",
            "password_confirm": "Password@123",
        }, format="json")
        self.assertEqual(registration.status_code, status.HTTP_202_ACCEPTED)
        self.assertNotIn("verification_email_sent", registration.data)
        user = User.objects.get(email="unverified.manual@example.com")
        original_id = user.pk
        original_profile_id = user.profile.pk
        mock_verify.return_value = {
            "iss": "https://accounts.google.com",
            "sub": "google-sub-unverified-manual",
            "email": "unverified.manual@example.com",
            "email_verified": True,
        }

        response = self.client.post("/api/accounts/google-login/", {"id_token": "verified-token"})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(response.data["mfa_required"])
        self.assertTrue(response.data["mfa_setup_required"])
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertEqual(User.objects.filter(email__iexact=user.email).count(), 1)
        user.refresh_from_db()
        user.profile.refresh_from_db()
        self.assertTrue(user.profile.email_verified)
        self.assertEqual(user.profile.google_sub, "google-sub-unverified-manual")

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="test-google-client-id")
    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_login_rejects_unverified_google_email_claim(self, mock_verify):
        user = User.objects.create_user(
            username="unverified_google_email",
            email="local.account@example.com",
            password="Password@123",
        )
        mock_verify.return_value = {
            "iss": "https://accounts.google.com",
            "sub": "google-sub-unverified-email",
            "email": "local.account@example.com",
            "email_verified": False,
        }

        response = self.client.post("/api/accounts/google-login/", {"id_token": "unverified-token"})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        user.refresh_from_db()
        user.profile.refresh_from_db()
        self.assertFalse(user.profile.email_verified)
        self.assertFalse(user.profile.google_sub)

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="test-google-client-id")
    @patch("google.oauth2.id_token.verify_oauth2_token", side_effect=ValueError("expired"))
    def test_google_login_rejects_invalid_or_expired_id_token(self, mock_verify):
        response = self.client.post("/api/accounts/google-login/", {"id_token": "expired-token"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(mock_verify.call_args.kwargs["audience"], "test-google-client-id")

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="test-google-client-id")
    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_login_invalid_issuer_rejected(self, mock_verify):
        """Invalid token issuer is rejected."""
        mock_verify.return_value = {
            "iss": "https://fakeissuer.com",
            "sub": "bad-sub",
            "email": "bad@example.com",
            "email_verified": True,
        }
        res = self.client.post("/api/accounts/google-login/", {
            "id_token": "bad-token",
        })
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_set_manual_password_flow(self):
        """Authenticated Google user can set a manual password and later sign in with password."""
        google_user = User.objects.create_user(
            username="googlepassuser",
            email="googlepassuser@example.com",
        )
        google_user.set_unusable_password()
        google_user.save()
        google_user.profile.google_sub = "google-sub-pass"
        google_user.profile.save()

        self.client.force_authenticate(user=google_user)

        # Mismatched passwords rejected
        res_mismatch = self.client.post("/api/accounts/set-password/", {
            "password": "Password@123",
            "password_confirm": "Different@123",
        })
        self.assertEqual(res_mismatch.status_code, status.HTTP_400_BAD_REQUEST)

        # Valid password set successfully
        res = self.client.post("/api/accounts/set-password/", {
            "password": "NewSecurePassword@123",
            "password_confirm": "NewSecurePassword@123",
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["user"]["has_usable_password"])

        google_user.refresh_from_db()
        self.assertTrue(google_user.has_usable_password())
        self.assertTrue(google_user.check_password("NewSecurePassword@123"))

        # A Google-only account still follows the existing email-verification
        # gate before password login can enroll MFA.
        google_user.profile.email_verified = True
        google_user.profile.save(update_fields=["email_verified", "updated_at"])

        # Cannot overwrite existing password silently
        res_repeat = self.client.post("/api/accounts/set-password/", {
            "password": "AnotherPassword@123",
            "password_confirm": "AnotherPassword@123",
        })
        self.assertEqual(res_repeat.status_code, status.HTTP_400_BAD_REQUEST)

        # Now, manual login with new password requires MFA enrollment
        self.client.logout()
        login_res = self.client.post("/api/accounts/login/", {
            "username": "googlepassuser@example.com",
            "password": "NewSecurePassword@123",
        })
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        self.assertTrue(login_res.data["mfa_required"])
        self.assertTrue(login_res.data["mfa_setup_required"])
        self.assertIn("challenge", login_res.data)
        self.assertIn("qr_code", login_res.data)

        # Complete MFA enrollment
        challenge = login_res.data["challenge"]
        secret = login_res.data["secret"]
        code = pyotp.TOTP(secret).now()

        verify_res = self.client.post("/api/accounts/login/", {
            "challenge": challenge,
            "code": code,
        })
        self.assertEqual(verify_res.status_code, status.HTTP_200_OK)
        self.assertIn("access", verify_res.data)
        self.assertIn("refresh", verify_res.data)
        google_user.profile.refresh_from_db()
        self.assertTrue(google_user.profile.mfa_enabled)

    def test_set_manual_password_rejected_for_non_google_users(self):
        """Non-Google users cannot call set-password endpoint."""
        normal_user = User.objects.create_user(
            username="regularuser",
            email="regularuser@example.com",
            password="InitialPassword123!",
        )
        self.client.force_authenticate(user=normal_user)
        res = self.client.post("/api/accounts/set-password/", {
            "password": "NewManualPassword123!",
            "password_confirm": "NewManualPassword123!",
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("only available for google-authenticated accounts", res.data["detail"].lower())

    def test_has_unclaimed_certificates_flag(self):
        """UserProfileSerializer reports has_unclaimed_certificates accurately."""
        from apps.certificates.models import Certificate
        from apps.accounts.serializers import UserProfileSerializer

        user = User.objects.create_user(
            username="unclaimedcheck",
            email="unclaimedcheck@example.com",
            password="Password123!",
        )
        profile = user.profile
        # Initially false: no certificates exist
        data = UserProfileSerializer(profile).data
        self.assertFalse(data["has_unclaimed_certificates"])

        # Create an unclaimed certificate with matching recipient_email
        Certificate.objects.create(
            certificate_number="CERT-UNCLAIM-001",
            title="Python Cert",
            issuer="OneSmarter",
            recipient_name="Check User",
            recipient_email="unclaimedcheck@example.com",
            issue_date=timezone.now().date(),
            owner=None,
            status=Certificate.Status.VERIFIED,
        )

        data_with_unclaimed = UserProfileSerializer(profile).data
        self.assertTrue(data_with_unclaimed["has_unclaimed_certificates"])

        # Once verified, it should be false (no longer blocked by email verification)
        profile.email_verified = True
        profile.save()
        data_verified = UserProfileSerializer(profile).data
        self.assertFalse(data_verified["has_unclaimed_certificates"])
