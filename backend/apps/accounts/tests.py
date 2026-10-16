import hashlib
import json
from datetime import timedelta
from unittest.mock import patch

import pyotp
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import MFARecoveryToken, PasswordResetRequest, PasswordResetToken, UserProfile
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

        # Create admin user
        self.admin = User.objects.create_superuser(
            username="superadmin",
            email="superadmin@example.com",
            password="AdminPassword@123",
            first_name="Super",
            last_name="Admin",
        )

        # Create staff user
        self.staff = User.objects.create_user(
            username="staffadmin",
            email="staffadmin@example.com",
            password="StaffPassword@123",
            is_staff=True,
            first_name="Staff",
            last_name="Admin",
        )

    def tear_buffer(self):
        cache.clear()

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
        res = self.client.post("/api/accounts/login/", {
            "username": "normaluser",
            "password": "Password@123",
        })
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

    def test_registration_creates_user_with_user_role(self):
        """New accounts registered through website always have USER role and cannot be staff."""
        res = self.client.post("/api/accounts/register/", {
            "username": "newbie",
            "email": "newbie@example.com",
            "first_name": "New",
            "last_name": "Bie",
            "password": "NewPassword@123",
            "password_confirm": "NewPassword@123",
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        new_user = User.objects.get(username="newbie")
        self.assertFalse(new_user.is_staff)
        self.assertFalse(new_user.is_superuser)
        self.assertEqual(new_user.profile.role, "USER")

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
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", res.data)

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
        confirm_res = self.client.post("/api/accounts/mfa/confirm/", {"code": code})
        self.assertEqual(confirm_res.status_code, status.HTTP_200_OK)

        profile = UserProfile.objects.get(user=self.user)
        self.assertTrue(profile.mfa_enabled)
        self.assertEqual(profile.totp_secret, secret)

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
        self.assertIn("/reset-password?token=", mail.outbox[0].body)

        # Unknown email request (clear cache cooldown first for testing)
        cache.clear()
        res2 = self.client.post("/api/accounts/password-reset/request/", {
            "email": "unknown@example.com",
        })
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertIn("reset", res2.data["detail"].lower())
        # No extra email sent
        self.assertEqual(len(mail.outbox), 1)

    def test_password_reset_cooldown(self):
        """Requesting password reset twice in under 60 seconds triggers cooldown."""
        res1 = self.client.post("/api/accounts/password-reset/request/", {
            "email": "normaluser@example.com",
        })
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        res2 = self.client.post("/api/accounts/password-reset/request/", {
            "email": "normaluser@example.com",
        })
        self.assertEqual(res2.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_full_password_reset_workflow(self):
        """End-to-end flow: request OTP -> verify OTP -> set new password -> sign in with new password."""
        mail.outbox = []
        user = self.user

        # Ensure user has MFA enabled to verify MFA preservation
        user.profile.mfa_enabled = True
        user.profile.totp_secret = pyotp.random_base32()
        user.profile.save()

        # Step 1: Request OTP
        req_res = self.client.post("/api/accounts/password-reset/request/", {
            "email": "normaluser@example.com",
        })
        self.assertEqual(req_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

        # Retrieve request record and set deterministic OTP
        reset_req = PasswordResetRequest.objects.filter(user=user, is_completed=False).first()
        self.assertIsNotNone(reset_req)
        test_otp = "852963"
        reset_req.otp_hash = hashlib.sha256(test_otp.encode("utf-8")).hexdigest()
        reset_req.save()

        # Step 2: Verify OTP
        verify_res = self.client.post("/api/accounts/password-reset/verify/", {
            "email": "normaluser@example.com",
            "otp": test_otp,
        })
        self.assertEqual(verify_res.status_code, status.HTTP_200_OK)
        self.assertIn("reset_token", verify_res.data)
        reset_token = verify_res.data["reset_token"]

        # Step 3: Complete password reset
        new_password = "BrandNewStrongPassword@2026"
        complete_res = self.client.post("/api/accounts/password-reset/complete/", {
            "reset_token": reset_token,
            "password": new_password,
            "password_confirm": new_password,
        })
        self.assertEqual(complete_res.status_code, status.HTTP_200_OK)
        self.assertIn("changed successfully", complete_res.data["detail"].lower())

        # Reset record is marked completed
        reset_req.refresh_from_db()
        self.assertTrue(reset_req.is_completed)

        # Confirmation email sent
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("Password Has Been Changed", mail.outbox[1].subject)

        # Old password no longer works
        old_login = self.client.post("/api/accounts/login/", {
            "username": "normaluser@example.com",
            "password": "Password@123",
        })
        self.assertEqual(old_login.status_code, status.HTTP_401_UNAUTHORIZED)

        # New password works and still requires MFA!
        new_login = self.client.post("/api/accounts/login/", {
            "username": "normaluser@example.com",
            "password": new_password,
        })
        self.assertEqual(new_login.status_code, status.HTTP_200_OK)
        self.assertTrue(new_login.data["mfa_required"])
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.mfa_enabled)

    def test_password_reset_otp_attempt_limits(self):
        """Entering incorrect OTP reaches maximum attempt limit and locks request."""
        # Create reset request
        test_otp = "123456"
        reset_req = PasswordResetRequest.objects.create(
            user=self.user,
            otp_hash=hashlib.sha256(test_otp.encode("utf-8")).hexdigest(),
            otp_expires_at=timezone.now() + timedelta(minutes=10),
            attempts=0,
            max_attempts=3,
        )

        for attempt in range(1, 3):
            res = self.client.post("/api/accounts/password-reset/verify/", {
                "email": "normaluser@example.com",
                "otp": "000000",
            })
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("remaining", res.data["detail"].lower())

        # 3rd failed attempt blocks the request
        res_final = self.client.post("/api/accounts/password-reset/verify/", {
            "email": "normaluser@example.com",
            "otp": "000000",
        })
        self.assertEqual(res_final.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("maximum verification attempts exceeded", res_final.data["detail"].lower())
        reset_req.refresh_from_db()
        self.assertTrue(reset_req.is_completed)

    def test_password_reset_expired_otp_rejected(self):
        """Expired OTP is rejected."""
        test_otp = "123456"
        PasswordResetRequest.objects.create(
            user=self.user,
            otp_hash=hashlib.sha256(test_otp.encode("utf-8")).hexdigest(),
            otp_expires_at=timezone.now() - timedelta(minutes=1),
            attempts=0,
        )

        res = self.client.post("/api/accounts/password-reset/verify/", {
            "email": "normaluser@example.com",
            "otp": test_otp,
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expired", res.data["detail"].lower())

    def test_password_reset_mismatched_passwords_rejected(self):
        """Mismatched passwords in completion step must be rejected."""
        raw_token = "valid_reset_token"
        PasswordResetRequest.objects.create(
            user=self.user,
            otp_hash="dummy_hash",
            reset_token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
            otp_expires_at=timezone.now() + timedelta(minutes=10),
            reset_token_expires_at=timezone.now() + timedelta(minutes=15),
            otp_verified=True,
            is_completed=False,
        )

        res = self.client.post("/api/accounts/password-reset/complete/", {
            "reset_token": raw_token,
            "password": "Password1@Strong",
            "password_confirm": "DifferentPassword2@Strong",
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password_confirm", res.data)

    def test_password_reset_reused_token_rejected(self):
        """Reusing an already consumed reset token is rejected."""
        raw_token = "already_consumed_token"
        PasswordResetRequest.objects.create(
            user=self.user,
            otp_hash="dummy_hash",
            reset_token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
            otp_expires_at=timezone.now() + timedelta(minutes=10),
            reset_token_expires_at=timezone.now() + timedelta(minutes=15),
            otp_verified=True,
            is_completed=True,
        )

        res = self.client.post("/api/accounts/password-reset/complete/", {
            "reset_token": raw_token,
            "password": "ValidNewPassword@123",
            "password_confirm": "ValidNewPassword@123",
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_password_reset_preserves_admin_role_and_mfa(self):
        """Admin user can reset password, ADMIN role and MFA status remain fully preserved."""
        mail.outbox = []
        admin = self.admin
        admin.profile.mfa_enabled = True
        admin.profile.totp_secret = pyotp.random_base32()
        admin.profile.save()

        # Step 1: Request
        self.client.post("/api/accounts/password-reset/request/", {
            "email": "superadmin@example.com",
        })
        req = PasswordResetRequest.objects.filter(user=admin, is_completed=False).first()
        self.assertIsNotNone(req)
        test_otp = "777888"
        req.otp_hash = hashlib.sha256(test_otp.encode("utf-8")).hexdigest()
        req.save()

        # Step 2: Verify
        v_res = self.client.post("/api/accounts/password-reset/verify/", {
            "email": "superadmin@example.com",
            "otp": test_otp,
        })
        token = v_res.data["reset_token"]

        # Step 3: Complete
        new_pass = "SuperAdminNewPass@999"
        c_res = self.client.post("/api/accounts/password-reset/complete/", {
            "reset_token": token,
            "password": new_pass,
            "password_confirm": new_pass,
        })
        self.assertEqual(c_res.status_code, status.HTTP_200_OK)

        # Admin status and role preserved
        admin.refresh_from_db()
        self.assertTrue(admin.is_superuser)
        self.assertEqual(admin.profile.role, "ADMIN")
        self.assertTrue(admin.profile.mfa_enabled)

    def test_password_reset_weak_password_rejected_by_validators(self):
        """Common or numeric passwords must be rejected by Django's password validators."""
        raw_token = "valid_weak_test_token"
        PasswordResetRequest.objects.create(
            user=self.user,
            otp_hash="dummy_hash",
            reset_token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
            otp_expires_at=timezone.now() + timedelta(minutes=10),
            reset_token_expires_at=timezone.now() + timedelta(minutes=15),
            otp_verified=True,
            is_completed=False,
        )

        res = self.client.post("/api/accounts/password-reset/complete/", {
            "reset_token": raw_token,
            "password": "123",
            "password_confirm": "123",
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", res.data)

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

    def test_duplicate_email_accounts_safety_prevented(self):
        """If database contains duplicate active accounts with same email, recovery and reset do not arbitrarily pick one."""
        # Create a second user with the same email
        User.objects.create_user(
            username="second_dup_user",
            email="normaluser@example.com",
            password="OtherPassword@123",
        )
        mail.outbox = []

        # MFA recovery request returns generic 200 but sends no email for safety
        res_mfa = self.client.post("/api/accounts/mfa/recovery/request/", {
            "email": "normaluser@example.com",
        })
        self.assertEqual(res_mfa.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)

        # Password reset request also sends no email
        cache.clear()
        res_pw = self.client.post("/api/accounts/password-reset/request/", {
            "email": "normaluser@example.com",
        })
        self.assertEqual(res_pw.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)

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
        self.assertIn("/reset-password?token=", mail.outbox[0].body)

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



