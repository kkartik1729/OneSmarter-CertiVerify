import base64
import hashlib
import io
import logging
import secrets
from datetime import timedelta

import pyotp
import qrcode

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken, Token

from .emails import (
    EmailDeliveryError,
    SMTPConfigurationError,
    send_mfa_recovery_email,
    send_mfa_reset_notification_email,
    send_password_changed_notification_email,
    send_password_reset_email,
    send_password_reset_otp_email,
    send_email_verification_otp_email,
)
from .models import EmailVerificationToken, MFARecoveryToken, PasswordResetRequest, PasswordResetToken, UserProfile
from .serializers import RegisterSerializer, UserProfileSerializer

logger = logging.getLogger(__name__)
User = get_user_model()


def get_client_ip(request):
    """Retrieve client IP address for rate limiting."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "127.0.0.1")


def get_or_sync_profile(user):
    """
    Ensure a UserProfile exists for the user and that admin/superuser roles
    are synchronized accurately. Standard users maintain the USER role.
    """
    is_admin_user = bool(user.is_superuser or user.is_staff)
    default_role = UserProfile.Role.ADMIN if is_admin_user else UserProfile.Role.USER
    profile, created = UserProfile.objects.get_or_create(
        user=user,
        defaults={"role": default_role},
    )
    if is_admin_user and profile.role != UserProfile.Role.ADMIN:
        profile.role = UserProfile.Role.ADMIN
        profile.save(update_fields=["role", "updated_at"])
    return profile


class MFAChallengeToken(Token):
    """Temporary token used only for MFA login and recovery steps."""

    token_type = "mfa_challenge"
    lifetime = timedelta(minutes=5)


class RegisterView(generics.CreateAPIView):
    """Register a new standard user and send email verification OTP."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate 6-digit OTP and token
        otp = f"{secrets.randbelow(1_000_000):06d}"
        otp_hash = hashlib.sha256(otp.encode("utf-8")).hexdigest()
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

        EmailVerificationToken.objects.create(
            user=user,
            token_hash=token_hash,
            otp_hash=otp_hash,
            expires_at=timezone.now() + timedelta(hours=24),
        )

        try:
            send_email_verification_otp_email(user, otp)
        except Exception as e:
            logger.warning("Failed to send verification email to %s: %s", user.email, e)

        headers = self.get_success_headers(serializer.data)
        return Response(
            {
                "user": serializer.data,
                "message": "Registration successful. Please verify your email using the verification code sent to your inbox.",
                "email": user.email,
            },
            status=status.HTTP_201_CREATED,
            headers=headers,
        )


class CurrentUserView(APIView):
    """Get or update the logged-in user's profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = get_or_sync_profile(request.user)
        return Response(UserProfileSerializer(profile).data)

    def patch(self, request):
        profile = get_or_sync_profile(request.user)

        serializer = UserProfileSerializer(
            profile,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)


class MFASetupView(APIView):
    """Generate a QR code for Google and Microsoft Authenticator enrollment."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = get_or_sync_profile(request.user)

        if profile.mfa_enabled:
            return Response(
                {"detail": "MFA is already enabled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        secret = pyotp.random_base32()
        profile.pending_totp_secret = secret
        profile.save(
            update_fields=["pending_totp_secret", "updated_at"]
        )

        provisioning_uri = pyotp.TOTP(secret).provisioning_uri(
            name=request.user.email or request.user.username,
            issuer_name="OneSmarter-CertiVerify",
        )

        qr_image = qrcode.make(provisioning_uri)
        buffer = io.BytesIO()
        qr_image.save(buffer, format="PNG")

        encoded_qr = base64.b64encode(
            buffer.getvalue()
        ).decode("ascii")

        return Response({
            "qr_code": f"data:image/png;base64,{encoded_qr}",
            "secret": secret,
            "message": (
                "Scan this QR code with Google Authenticator or Microsoft Authenticator, "
                "then enter the six-digit code to confirm setup."
            ),
        })


class MFAConfirmView(APIView):
    """Verify the first authenticator code and enable MFA."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = str(request.data.get("code", "")).strip()

        if not (code.isdigit() and len(code) == 6):
            return Response(
                {"detail": "Enter the six-digit authenticator code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile = get_or_sync_profile(request.user)

        if profile.mfa_enabled:
            return Response(
                {"detail": "MFA is already enabled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        secret = profile.pending_totp_secret

        if not secret or not pyotp.TOTP(secret).verify(
            code,
            valid_window=1,
        ):
            return Response(
                {
                    "detail": (
                        "Invalid code. Check your authenticator app "
                        "and try again."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile.totp_secret = secret
        profile.pending_totp_secret = ""
        profile.mfa_enabled = True
        profile.mfa_enabled_at = timezone.now()

        profile.save(
            update_fields=[
                "totp_secret",
                "pending_totp_secret",
                "mfa_enabled",
                "mfa_enabled_at",
                "updated_at",
            ]
        )

        return Response({
            "detail": "Authenticator MFA enabled successfully."
        })


class MFALoginView(APIView):
    """
    Step 1: Validate username and password.
    Step 2: Validate the MFA challenge and six-digit code.
    Issue JWT tokens only after successful verification.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        challenge = str(
            request.data.get("challenge", "")
        ).strip()

        # Step 2: Complete MFA verification / enrollment.
        if challenge:
            code = str(request.data.get("code", "")).strip()

            try:
                token = MFAChallengeToken(challenge)
                user_id = token[api_settings.USER_ID_CLAIM]

                user = User.objects.get(
                    **{api_settings.USER_ID_FIELD: user_id}
                )

            except (
                TokenError,
                User.DoesNotExist,
                KeyError,
                TypeError,
                ValueError,
            ):
                return Response(
                    {"detail": "Invalid or expired MFA challenge."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            purpose = token.get("purpose")
            if purpose not in ("mfa_challenge", "mfa_setup_challenge"):
                return Response(
                    {"detail": "Invalid MFA challenge."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            if not user.is_active:
                return Response(
                    {"detail": "This account is inactive."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            profile = get_or_sync_profile(user)

            is_setup = purpose == "mfa_setup_challenge"
            secret = profile.pending_totp_secret if is_setup else profile.totp_secret

            if not secret:
                return Response(
                    {"detail": "MFA is not configured or setup expired. Please login again."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            jti = str(token["jti"])
            used_key = f"certiverify:mfa:used:{jti}"
            attempts_key = f"certiverify:mfa:attempts:{jti}"

            if cache.get(used_key):
                return Response(
                    {"detail": "This challenge has already been used."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            attempts = cache.get(attempts_key, 0)

            if attempts >= 5:
                return Response(
                    {"detail": "Too many attempts. Start login again."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            cache.set(attempts_key, attempts + 1, timeout=300)

            # Replay protection: check if code was already used for this user recently
            otp_used_key = f"certiverify:otp:used:{user.id}:{code}"
            if cache.get(otp_used_key):
                return Response(
                    {"detail": "This code has already been used. Please wait for the next code."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            valid_code = (
                code.isdigit()
                and len(code) == 6
                and pyotp.TOTP(secret).verify(
                    code,
                    valid_window=1,
                )
            )

            if not valid_code:
                return Response(
                    {"detail": "Invalid authenticator code. Check Google or Microsoft Authenticator and try again."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            # Mark code as used for 60 seconds to prevent replay
            cache.set(otp_used_key, True, timeout=60)

            # Consume this challenge before issuing JWT tokens.
            cache.set(used_key, True, timeout=300)

            # If this was setup enrollment, commit to profile now
            if is_setup:
                profile.totp_secret = secret
                profile.pending_totp_secret = ""
                profile.mfa_enabled = True
                profile.mfa_enabled_at = timezone.now()
                profile.save(
                    update_fields=[
                        "totp_secret",
                        "pending_totp_secret",
                        "mfa_enabled",
                        "mfa_enabled_at",
                        "updated_at",
                    ]
                )

            refresh = RefreshToken.for_user(user)

            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "mfa_required": False,
            })

        # Step 1: Validate username and password.
        username = str(request.data.get("username", "")).strip()
        password = str(request.data.get("password", ""))

        user = authenticate(
            request=request,
            username=username,
            password=password,
        )

        # Allow sign-in by email if username authentication failed
        if user is None and "@" in username:
            user_by_email = User.objects.filter(email__iexact=username).first()
            if user_by_email and user_by_email.check_password(password):
                user = user_by_email

        if user is None or not user.is_active:
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        profile = get_or_sync_profile(user)

        # If user already has MFA enabled, prompt for 6-digit code
        if profile.mfa_enabled and profile.totp_secret:
            challenge_token = MFAChallengeToken()
            challenge_token[api_settings.USER_ID_CLAIM] = getattr(
                user,
                api_settings.USER_ID_FIELD,
            )
            challenge_token["purpose"] = "mfa_challenge"

            return Response({
                "mfa_required": True,
                "mfa_setup_required": False,
                "challenge": str(challenge_token),
                "detail": (
                    "Enter the six-digit code from Google Authenticator or Microsoft Authenticator to complete login."
                ),
            })

        # If user has NOT set up MFA yet, generate QR code and require TOTP confirmation immediately
        secret = pyotp.random_base32()
        profile.pending_totp_secret = secret
        profile.save(
            update_fields=["pending_totp_secret", "updated_at"]
        )

        provisioning_uri = pyotp.TOTP(secret).provisioning_uri(
            name=user.email or user.username,
            issuer_name="OneSmarter-CertiVerify",
        )

        qr_image = qrcode.make(provisioning_uri)
        buffer = io.BytesIO()
        qr_image.save(buffer, format="PNG")
        encoded_qr = base64.b64encode(buffer.getvalue()).decode("ascii")

        challenge_token = MFAChallengeToken()
        challenge_token[api_settings.USER_ID_CLAIM] = getattr(
            user,
            api_settings.USER_ID_FIELD,
        )
        challenge_token["purpose"] = "mfa_setup_challenge"

        return Response({
            "mfa_required": True,
            "mfa_setup_required": True,
            "challenge": str(challenge_token),
            "qr_code": f"data:image/png;base64,{encoded_qr}",
            "secret": secret,
            "detail": (
                "Scan this QR code with Google Authenticator or Microsoft Authenticator, then enter the six-digit code to complete login."
            ),
        })


class MFAVerifyView(MFALoginView):
    """Endpoint for completing MFA login with a challenge and code."""

    def post(self, request):
        challenge = str(
            request.data.get("challenge", "")
        ).strip()
        code = str(request.data.get("code", "")).strip()

        if not challenge:
            return Response(
                {"detail": "The MFA challenge token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not (code.isdigit() and len(code) == 6):
            return Response(
                {"detail": "Enter the six-digit authenticator code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().post(request)


class MFARecoveryRequestView(APIView):
    """
    Initiate email-based MFA recovery for lost authenticator access.
    Returns generic response to prevent user enumeration.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()

        if not email or "@" not in email:
            return Response(
                {"detail": "Enter a valid registered email address."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Rate limiting: max 5 requests per 15 minutes per IP
        client_ip = get_client_ip(request)
        rate_key = f"certiverify:recovery:rate:{client_ip}"
        requests_count = cache.get(rate_key, 0)
        if requests_count >= 5:
            return Response(
                {"detail": "Too many recovery requests. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        cache.set(rate_key, requests_count + 1, timeout=900)

        # Generic response message (always identical to prevent account enumeration)
        generic_msg = (
            "If an account with that email address exists, "
            "instructions to recover your authenticator have been sent."
        )

        matching_users = User.objects.filter(email__iexact=email, is_active=True)
        if matching_users.count() == 1:
            user = matching_users.first()
            # Invalidate any outstanding unused recovery tokens for this user
            MFARecoveryToken.objects.filter(user=user, is_used=False).update(is_used=True)

            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

            MFARecoveryToken.objects.create(
                user=user,
                token_hash=token_hash,
                expires_at=timezone.now() + timedelta(minutes=15),
                purpose="mfa_recovery",
            )

            frontend_base = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
            recovery_url = f"{frontend_base}/mfa-recovery?token={raw_token}"

            try:
                send_mfa_recovery_email(user, recovery_url)
            except SMTPConfigurationError as e:
                logger.warning(f"SMTP configuration error sending MFA recovery email to {email}: {e}")
                if getattr(settings, "DEBUG", False):
                    return Response(
                        {
                            "detail": (
                                "SMTP is not fully configured on the server. "
                                "Please configure EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in backend/.env."
                            )
                        },
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                return Response(
                    {"detail": "Unable to dispatch email due to mail server configuration error."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            except EmailDeliveryError as e:
                logger.error(f"Error sending MFA recovery email to {email}: {e}")
                return Response(
                    {"detail": "Failed to send recovery email due to a mail server error. Please try again later."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        elif matching_users.count() > 1:
            logger.warning(
                f"Multiple active accounts found with email '{email}'. "
                "Refusing automatic recovery to avoid arbitrary account compromise."
            )

        return Response({"detail": generic_msg}, status=status.HTTP_200_OK)


class MFARecoveryConfirmView(APIView):
    """
    Validate the recovery token from the email link and initiate new authenticator provisioning.
    Does NOT reset or disable MFA yet until new TOTP code is confirmed.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        token_str = str(request.data.get("token", "")).strip()
        if not token_str:
            return Response(
                {"detail": "Recovery token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token_hash = hashlib.sha256(token_str.encode("utf-8")).hexdigest()
        recovery_record = (
            MFARecoveryToken.objects.filter(token_hash=token_hash)
            .select_related("user")
            .first()
        )

        if not recovery_record or not recovery_record.is_valid():
            return Response(
                {
                    "detail": (
                        "This recovery link is invalid, expired, or has already been used. "
                        "Please request a new recovery link."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = recovery_record.user
        if not user.is_active:
            return Response(
                {"detail": "This account is inactive."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        profile = get_or_sync_profile(user)

        # Generate a new TOTP secret for re-enrollment in pending state
        new_secret = pyotp.random_base32()
        profile.pending_totp_secret = new_secret
        profile.save(update_fields=["pending_totp_secret", "updated_at"])

        provisioning_uri = pyotp.TOTP(new_secret).provisioning_uri(
            name=user.email or user.username,
            issuer_name="OneSmarter-CertiVerify",
        )

        qr_image = qrcode.make(provisioning_uri)
        buffer = io.BytesIO()
        qr_image.save(buffer, format="PNG")
        encoded_qr = base64.b64encode(buffer.getvalue()).decode("ascii")

        challenge_token = MFAChallengeToken()
        challenge_token[api_settings.USER_ID_CLAIM] = getattr(
            user,
            api_settings.USER_ID_FIELD,
        )
        challenge_token["purpose"] = "mfa_recovery_session"
        challenge_token["recovery_token_id"] = recovery_record.id

        return Response({
            "challenge": str(challenge_token),
            "qr_code": f"data:image/png;base64,{encoded_qr}",
            "secret": new_secret,
            "email": user.email,
            "detail": (
                "Scan this new QR code with Google Authenticator or Microsoft Authenticator, "
                "then enter the six-digit code to complete recovery."
            ),
        })


class MFARecoveryCompleteView(APIView):
    """
    Confirm the new authenticator code, finalize recovery, invalidate the recovery token,
    and issue JWT authentication tokens with the original role preserved.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        challenge = str(request.data.get("challenge", "")).strip()
        code = str(request.data.get("code", "")).strip()

        if not challenge:
            return Response(
                {"detail": "Challenge token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not (code.isdigit() and len(code) == 6):
            return Response(
                {"detail": "Enter the six-digit authenticator code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = MFAChallengeToken(challenge)
            user_id = token[api_settings.USER_ID_CLAIM]
            user = User.objects.get(**{api_settings.USER_ID_FIELD: user_id})
        except Exception:
            return Response(
                {"detail": "Invalid or expired recovery challenge."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if token.get("purpose") != "mfa_recovery_session":
            return Response(
                {"detail": "Invalid recovery challenge purpose."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        recovery_token_id = token.get("recovery_token_id")
        recovery_record = MFARecoveryToken.objects.filter(
            id=recovery_token_id,
            user=user,
        ).first()

        if not recovery_record or not recovery_record.is_valid():
            return Response(
                {"detail": "Recovery session is expired or already used."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile = get_or_sync_profile(user)
        secret = profile.pending_totp_secret

        if not secret:
            return Response(
                {"detail": "Setup secret expired. Please start recovery again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_code = pyotp.TOTP(secret).verify(code, valid_window=1)
        if not valid_code:
            return Response(
                {
                    "detail": (
                        "Invalid code. Check your new Google Authenticator or "
                        "Microsoft Authenticator entry and try again."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Permanently invalidate the recovery token
        recovery_record.is_used = True
        recovery_record.used_at = timezone.now()
        recovery_record.save(update_fields=["is_used", "used_at"])

        # Also invalidate any remaining recovery tokens for this user
        MFARecoveryToken.objects.filter(user=user, is_used=False).update(is_used=True)

        # Enable the new secret; role is strictly preserved
        profile.totp_secret = secret
        profile.pending_totp_secret = ""
        profile.mfa_enabled = True
        profile.mfa_enabled_at = timezone.now()
        profile.save(
            update_fields=[
                "totp_secret",
                "pending_totp_secret",
                "mfa_enabled",
                "mfa_enabled_at",
                "updated_at",
            ]
        )

        # Send security notification email
        try:
            send_mfa_reset_notification_email(user)
        except Exception as e:
            logger.error(f"Error sending recovery confirmation email: {e}")

        # Issue tokens for API compatibility; frontend guides user to Back to Sign In
        refresh = RefreshToken.for_user(user)

        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "detail": "MFA recovery complete. Your new authenticator has been enrolled and activated. Please sign in to continue.",
            "success": True,
        })


class PasswordResetRequestView(APIView):
    """
    Step 1 of password recovery:
    Accept email, generate a cryptographically secure single-use reset token,
    store its hash with 15-minute expiry in PostgreSQL, and send a branded email
    with a direct reset link to the website.
    Returns generic message to prevent account enumeration.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()

        if not email or "@" not in email:
            return Response(
                {"detail": "Enter a valid registered email address."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Rate limiting by IP (max 5 requests per 15 min)
        client_ip = get_client_ip(request)
        rate_key = f"certiverify:pwreset:rate:{client_ip}"
        requests_count = cache.get(rate_key, 0)
        if requests_count >= 5:
            return Response(
                {"detail": "Too many password reset requests. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        cache.set(rate_key, requests_count + 1, timeout=900)

        # Email cooldown (max 1 request per 60 seconds per email)
        cooldown_key = f"certiverify:pwreset:cooldown:{email}"
        if cache.get(cooldown_key):
            return Response(
                {"detail": "A reset link was recently requested. Please check your email or wait a moment."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        cache.set(cooldown_key, True, timeout=60)

        generic_msg = (
            "If an account with that email address exists, "
            "a password reset link has been sent to your email address."
        )

        matching_users = User.objects.filter(email__iexact=email, is_active=True)
        if matching_users.count() == 1:
            user = matching_users.first()

            # Invalidate older active password reset requests & tokens for this user
            PasswordResetToken.objects.filter(user=user, is_used=False).update(is_used=True)
            PasswordResetRequest.objects.filter(user=user, is_completed=False).update(is_completed=True)

            # Generate cryptographically secure single-use reset token
            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

            # Persist in dedicated PasswordResetToken model
            PasswordResetToken.objects.create(
                user=user,
                token_hash=token_hash,
                expires_at=timezone.now() + timedelta(minutes=15),
                purpose="password_reset",
            )

            # Also maintain legacy OTP record for backward compatibility
            otp = f"{secrets.randbelow(1000000):06d}"
            otp_hash = hashlib.sha256(otp.encode("utf-8")).hexdigest()
            PasswordResetRequest.objects.create(
                user=user,
                otp_hash=otp_hash,
                reset_token_hash=token_hash,
                otp_expires_at=timezone.now() + timedelta(minutes=10),
                reset_token_expires_at=timezone.now() + timedelta(minutes=15),
                attempts=0,
                max_attempts=5,
            )

            frontend_base = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
            reset_url = f"{frontend_base}/reset-password?token={raw_token}"

            try:
                send_password_reset_email(user, reset_url)
            except SMTPConfigurationError as e:
                logger.warning(f"SMTP configuration error sending password reset email to {email}: {e}")
                if getattr(settings, "DEBUG", False):
                    return Response(
                        {
                            "detail": (
                                "SMTP is not fully configured on the server. "
                                "Please configure EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in backend/.env."
                            )
                        },
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                return Response(
                    {"detail": "Unable to dispatch email due to mail server configuration error."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            except EmailDeliveryError as e:
                logger.error(f"Error sending password reset email to {email}: {e}")
                return Response(
                    {"detail": "Failed to send reset email due to a mail server error. Please try again later."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        elif matching_users.count() > 1:
            logger.warning(
                f"Multiple active accounts found with email '{email}'. "
                "Refusing automatic password reset for security."
            )

        return Response({"detail": generic_msg}, status=status.HTTP_200_OK)


class PasswordResetValidateTokenView(APIView):
    """
    Validate a password-reset token received via email link.
    Checks that the token exists, is unexpired, and has not been used.
    Does NOT modify state or reset the password.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def _validate_token_str(self, token_str: str):
        if not token_str:
            return Response(
                {"detail": "Password reset token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token_hash = hashlib.sha256(token_str.encode("utf-8")).hexdigest()

        # Check PasswordResetToken first
        reset_token_record = (
            PasswordResetToken.objects.filter(token_hash=token_hash)
            .select_related("user")
            .first()
        )
        if reset_token_record and reset_token_record.is_valid():
            if not reset_token_record.user.is_active:
                return Response(
                    {"detail": "This account is inactive."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            return Response(
                {
                    "valid": True,
                    "email": reset_token_record.user.email,
                    "detail": "Password reset token is valid.",
                },
                status=status.HTTP_200_OK,
            )

        # Fallback check PasswordResetRequest
        reset_req = (
            PasswordResetRequest.objects.filter(reset_token_hash=token_hash)
            .select_related("user")
            .first()
        )
        if reset_req and reset_req.is_reset_token_valid():
            if not reset_req.user.is_active:
                return Response(
                    {"detail": "This account is inactive."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            return Response(
                {
                    "valid": True,
                    "email": reset_req.user.email,
                    "detail": "Password reset token is valid.",
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "detail": (
                    "This password reset link is invalid, expired, or has already been used. "
                    "Please request a new reset link."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    def post(self, request):
        token_str = str(
            request.data.get("token") or request.data.get("reset_token") or ""
        ).strip()
        return self._validate_token_str(token_str)

    def get(self, request):
        token_str = str(
            request.query_params.get("token") or request.query_params.get("reset_token") or ""
        ).strip()
        return self._validate_token_str(token_str)


class PasswordResetVerifyView(APIView):
    """
    Step 2 of password recovery (supports both direct token check and OTP verification):
    - If 'token' is provided: validates the single-use reset token from email link.
    - If 'otp' is provided: validates 6-digit verification code and returns reset_token.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        token_param = str(
            request.data.get("token") or request.query_params.get("token") or ""
        ).strip()
        if token_param:
            validate_view = PasswordResetValidateTokenView()
            return validate_view._validate_token_str(token_param)

        email = str(request.data.get("email", "")).strip().lower()
        otp = str(request.data.get("otp", "")).strip()

        if not email or "@" not in email:
            return Response(
                {"detail": "Enter a valid email address."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not (otp.isdigit() and len(otp) == 6):
            return Response(
                {"detail": "Enter the 6-digit verification code sent to your email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        matching_users = User.objects.filter(email__iexact=email, is_active=True)
        if matching_users.count() != 1:
            return Response(
                {"detail": "Invalid or expired verification code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = matching_users.first()
        reset_req = (
            PasswordResetRequest.objects.filter(
                user=user,
                is_completed=False,
                otp_verified=False,
            )
            .order_by("-created_at")
            .first()
        )

        if not reset_req:
            return Response(
                {"detail": "No active password reset request found. Please request a new code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if timezone.now() > reset_req.otp_expires_at:
            reset_req.is_completed = True
            reset_req.save(update_fields=["is_completed"])
            return Response(
                {"detail": "Verification code has expired. Please request a new code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if reset_req.attempts >= reset_req.max_attempts:
            reset_req.is_completed = True
            reset_req.save(update_fields=["is_completed"])
            return Response(
                {"detail": "Maximum verification attempts exceeded. Please request a new code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        provided_hash = hashlib.sha256(otp.encode("utf-8")).hexdigest()
        if not secrets.compare_digest(provided_hash, reset_req.otp_hash):
            reset_req.attempts += 1
            reset_req.save(update_fields=["attempts"])
            remaining = reset_req.max_attempts - reset_req.attempts
            if remaining <= 0:
                reset_req.is_completed = True
                reset_req.save(update_fields=["is_completed"])
                return Response(
                    {"detail": "Maximum verification attempts exceeded. Please request a new code."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {"detail": f"Invalid verification code. {remaining} attempt(s) remaining."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Code is correct: mark verified and generate short-lived reset authorization token
        raw_reset_token = secrets.token_urlsafe(32)
        reset_req.otp_verified = True
        reset_req.reset_token_hash = hashlib.sha256(raw_reset_token.encode("utf-8")).hexdigest()
        reset_req.reset_token_expires_at = timezone.now() + timedelta(minutes=15)
        reset_req.save(
            update_fields=["otp_verified", "reset_token_hash", "reset_token_expires_at"]
        )

        # Also create PasswordResetToken for unified tracking
        PasswordResetToken.objects.create(
            user=user,
            token_hash=reset_req.reset_token_hash,
            expires_at=reset_req.reset_token_expires_at,
            purpose="password_reset",
        )

        return Response(
            {
                "reset_token": raw_reset_token,
                "detail": "Verification code accepted. Please enter your new password.",
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetCompleteView(APIView):
    """
    Step 3 of password recovery:
    Validate short-lived reset authorization token, enforce Django's configured
    password validators, set the new password in PostgreSQL, invalidate older reset sessions,
    and send confirmation notification email. MFA state is strictly preserved.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        reset_token = str(
            request.data.get("token") or request.data.get("reset_token") or ""
        ).strip()
        password = str(request.data.get("password", ""))
        password_confirm = str(request.data.get("password_confirm", ""))

        if not reset_token:
            return Response(
                {"detail": "Password reset authorization token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not password:
            return Response(
                {"password": ["Password is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if password != password_confirm:
            return Response(
                {"password_confirm": ["Passwords do not match."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token_hash = hashlib.sha256(reset_token.encode("utf-8")).hexdigest()

        # Check PasswordResetToken first
        token_record = (
            PasswordResetToken.objects.filter(token_hash=token_hash)
            .select_related("user")
            .first()
        )

        user = None
        if token_record and token_record.is_valid():
            user = token_record.user
        else:
            # Fallback to PasswordResetRequest for OTP flow
            reset_req = (
                PasswordResetRequest.objects.filter(
                    reset_token_hash=token_hash,
                    is_completed=False,
                )
                .select_related("user")
                .first()
            )
            if reset_req and reset_req.is_reset_token_valid():
                user = reset_req.user

        if not user:
            return Response(
                {
                    "detail": (
                        "This password reset session is invalid, expired, or has already been used. "
                        "Please request a new reset link."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.is_active:
            return Response(
                {"detail": "This account is inactive."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Enforce Django password validators
        try:
            validate_password(password, user=user)
        except DjangoValidationError as exc:
            return Response(
                {"password": list(exc.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Set new password
        user.set_password(password)
        user.save()

        # Invalidate the used token and all other outstanding reset tokens for this user
        if token_record:
            token_record.is_used = True
            token_record.used_at = timezone.now()
            token_record.save(update_fields=["is_used", "used_at"])
        PasswordResetToken.objects.filter(user=user, is_used=False).update(
            is_used=True, used_at=timezone.now()
        )
        PasswordResetRequest.objects.filter(user=user, is_completed=False).update(
            is_completed=True
        )

        # Send password changed confirmation email
        try:
            send_password_changed_notification_email(user)
        except Exception as e:
            logger.error(f"Error sending password changed notification email: {e}")

        return Response(
            {
                "detail": (
                    "Your password has been changed successfully. "
                    "Please sign in with your new password."
                )
            },
            status=status.HTTP_200_OK,
        )


class VerifyEmailView(APIView):
    """
    Verify a user's email address using 6-digit OTP or link token.
    Once email is verified, immediately triggers auto-claiming of any
    unclaimed certificates associated with this email.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        otp = str(request.data.get("otp", "")).strip()
        token = str(request.data.get("token", "")).strip()

        user = None
        if request.user and request.user.is_authenticated:
            user = request.user
        elif email:
            user = User.objects.filter(email__iexact=email).first()

        if not user:
            return Response(
                {"detail": "User not found or email required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not otp and not token:
            return Response(
                {"detail": "Verification code (OTP) or token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile = get_or_sync_profile(user)

        # Find matching token
        token_record = None
        now = timezone.now()
        active_tokens = EmailVerificationToken.objects.filter(
            user=user,
            is_used=False,
            expires_at__gte=now,
        ).order_by("-created_at")

        if otp:
            otp_hash = hashlib.sha256(otp.encode("utf-8")).hexdigest()
            token_record = active_tokens.filter(otp_hash=otp_hash).first()
        elif token:
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
            token_record = active_tokens.filter(token_hash=token_hash).first()

        if not token_record:
            return Response(
                {"detail": "Invalid or expired verification code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark token as used
        token_record.is_used = True
        token_record.used_at = now
        token_record.save(update_fields=["is_used", "used_at"])

        # Mark profile as email_verified
        profile.email_verified = True
        profile.email_verified_at = now
        profile.save(update_fields=["email_verified", "email_verified_at", "updated_at"])

        # Trigger auto-claiming of certificates
        from apps.certificates.services import claim_unclaimed_certificates_for_user
        claimed_certs = claim_unclaimed_certificates_for_user(user)

        return Response(
            {
                "detail": "Email verified successfully.",
                "email_verified": True,
                "claimed_count": len(claimed_certs),
                "claimed_certificate_numbers": [c.certificate_number for c in claimed_certs],
            },
            status=status.HTTP_200_OK,
        )


class ResendVerificationEmailView(APIView):
    """
    Resend email verification OTP to a registered user.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        user = None
        if request.user and request.user.is_authenticated:
            user = request.user
        elif email:
            user = User.objects.filter(email__iexact=email).first()

        if not user:
            # Prevent email enumeration: return standard success message even if not found
            return Response(
                {"detail": "If an account exists with this email, a verification code has been sent."},
                status=status.HTTP_200_OK,
            )

        profile = get_or_sync_profile(user)
        if profile.email_verified:
            return Response(
                {"detail": "Email is already verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Rate limit: check if a token was created in the last 60 seconds
        recent_token = EmailVerificationToken.objects.filter(
            user=user,
            created_at__gte=timezone.now() - timedelta(seconds=60),
        ).first()
        if recent_token:
            return Response(
                {"detail": "Please wait a moment before requesting another verification code."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Invalidate previous unused tokens
        EmailVerificationToken.objects.filter(user=user, is_used=False).update(
            is_used=True, used_at=timezone.now()
        )

        otp = f"{secrets.randbelow(1_000_000):06d}"
        otp_hash = hashlib.sha256(otp.encode("utf-8")).hexdigest()
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

        EmailVerificationToken.objects.create(
            user=user,
            token_hash=token_hash,
            otp_hash=otp_hash,
            expires_at=timezone.now() + timedelta(hours=24),
        )

        try:
            send_email_verification_otp_email(user, otp)
        except Exception as e:
            logger.warning("Failed to resend verification email to %s: %s", user.email, e)

        return Response(
            {"detail": "Verification code has been sent to your email."},
            status=status.HTTP_200_OK,
        )


