import base64

import hashlib

import io

import logging

import re

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
from django.db import IntegrityError, transaction
from django.db.models.functions import Lower, Trim

from django.utils import timezone



from rest_framework import generics, status

from rest_framework.permissions import AllowAny, IsAuthenticated

from rest_framework.response import Response

from rest_framework.views import APIView



from rest_framework_simplejwt.exceptions import TokenError

from rest_framework_simplejwt.settings import api_settings

from rest_framework_simplejwt.tokens import RefreshToken, Token



from .services import (

    EmailDeliveryError,

    SMTPConfigurationError,

    send_mfa_recovery_email,

    send_mfa_reset_notification_email,
    send_mfa_enabled_notification_email,

    send_password_changed_notification_email,

    send_password_reset_email,


    send_email_verification_otp_email,

)
from .authentication import issue_user_refresh_token
from .client_ip import get_client_ip

from .models import EmailVerificationToken, MFARecoveryToken, PasswordResetRequest, PasswordResetToken, UserProfile
from .throttles import (
    EmailVerificationIPThrottle,
    LoginIPThrottle,
    LoginIdentityThrottle,
    PasswordResetIPThrottle,
)

from .serializers import RegisterSerializer, UserProfileSerializer



logger = logging.getLogger(__name__)

User = get_user_model()





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







class LogoutView(APIView):
    """Blacklist a refresh token; invalid/stale tokens are harmless to retry."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        refresh_value = request.data.get("refresh")
        if isinstance(refresh_value, str) and refresh_value:
            try:
                RefreshToken(refresh_value).blacklist()
            except TokenError:
                # Logout is idempotent and must remain available to stale clients.
                pass
        return Response(status=status.HTTP_205_RESET_CONTENT)


class CurrentUserView(APIView):
    """Return the authenticated user's profile for the frontend."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = get_or_sync_profile(request.user)
        return Response(UserProfileSerializer(profile).data)

    def patch(self, request):
        profile = get_or_sync_profile(request.user)
        serializer = UserProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class MFAChallengeToken(Token):

    """Temporary token used only for MFA login and recovery steps."""



    token_type = "mfa_challenge"

    lifetime = timedelta(minutes=5)





class RegisterView(generics.CreateAPIView):

    """Register users and send an account verification code."""



    serializer_class = RegisterSerializer

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [EmailVerificationIPThrottle]



    def create(self, request, *args, **kwargs):

        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            email = str(request.data.get("email", "")).strip()
            username = str(request.data.get("username", "")).strip()
            identity_exists = bool(
                (email and User.objects.filter(email__iexact=email).exists())
                or (username and User.objects.filter(username__iexact=username).exists())
            )
            if identity_exists:
                return Response(
                    {"detail": "If registration can be completed, verification instructions will be sent to the matching email."},
                    status=status.HTTP_202_ACCEPTED,
                )
            serializer.is_valid(raise_exception=True)

        try:
            user = serializer.save()
        except IntegrityError:
            # A concurrent registration may win the uniqueness race after
            # validation. Keep the response indistinguishable from a duplicate.
            return Response(
                {"detail": "If registration can be completed, verification instructions will be sent to the matching email."},
                status=status.HTTP_202_ACCEPTED,
            )

        try:
            from apps.audit.models import AuditLog
            from apps.audit.services import log_action
            log_action(
                action=AuditLog.Action.USER_REGISTERED,
                actor=user,
                target_type="User",
                target_id=str(user.pk),
                description="Account registered; email verification is pending",
                ip_address=get_client_ip(request),
            )
        except Exception:
            logger.exception("Account was created but its audit event could not be recorded")



        otp = f"{secrets.randbelow(1_000_000):06d}"
        otp_hash = hashlib.sha256(otp.encode("utf-8")).hexdigest()
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        verification_record = EmailVerificationToken.objects.create(
            user=user,
            token_hash=token_hash,
            otp_hash=otp_hash,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        try:
            email_sent = bool(send_email_verification_otp_email(user, otp))
        except Exception:
            # Do not log OTPs, tokens, or credentials.
            logger.exception("Failed to send account verification email")
            email_sent = False
        if not email_sent:
            verification_record.is_used = True
            verification_record.used_at = timezone.now()
            verification_record.save(update_fields=["is_used", "used_at"])



        return Response(
            {"detail": "If registration can be completed, verification instructions will be sent to the matching email."},
            status=status.HTTP_202_ACCEPTED,
        )



class MFASetupView(APIView):
    """Generate a pending authenticator secret and QR code."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = get_or_sync_profile(request.user)

        if profile.mfa_enabled:
            return Response(
                {"detail": "MFA is already enabled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Reuse a pending secret if setup has already started.
        secret = profile.pending_totp_secret
        if not secret:
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
        encoded_qr = base64.b64encode(buffer.getvalue()).decode("ascii")

        return Response({
            "qr_code": f"data:image/png;base64,{encoded_qr}",
            "secret": secret,
            "mfa_enabled": False,
            "detail": (
                "Scan the QR code with Google Authenticator or "
                "Microsoft Authenticator, then confirm with a six-digit code."
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



        from apps.audit.models import AuditLog
        from apps.audit.services import log_action
        try:
            log_action(
                action=AuditLog.Action.MFA_ENABLED,
                actor=request.user,
                target_type="User",
                target_id=str(request.user.pk),
                description="Authenticator MFA enabled by account owner",
                ip_address=get_client_ip(request),
            )
        except Exception:
            logger.exception("MFA was enabled but its audit event could not be recorded")

        def send_enrollment_notice():
            try:
                send_mfa_enabled_notification_email(request.user)
            except Exception as exc:
                logger.warning("MFA enrollment notification failed (%s)", type(exc).__name__)

        transaction.on_commit(send_enrollment_notice)
        return Response({"detail": "Authenticator MFA enabled successfully."})





class MFALoginView(APIView):

    """

    Step 1: Validate username and password.

    Step 2: Validate the MFA challenge and six-digit code.

    Issue JWT tokens only after successful verification.

    """



    permission_classes = [AllowAny]

    authentication_classes = []

    throttle_classes = [LoginIPThrottle, LoginIdentityThrottle]



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

            if not profile.email_verified:
                return Response(
                    {"detail": "Verify your email address before signing in."},
                    status=status.HTTP_403_FORBIDDEN,
                )



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



            if not cache.add(attempts_key, 1, timeout=300):
                attempts = cache.incr(attempts_key)
            else:
                attempts = 1

            if attempts > 5:
                return Response(
                    {"detail": "Too many attempts. Start login again."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )



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

            # The verifier accepts the current TOTP step plus one step on
            # either side, so the replay marker must cover that full window.
            cache.set(otp_used_key, True, timeout=90)



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



            refresh = issue_user_refresh_token(user)
            user.last_login = timezone.now()
            user.save(update_fields=["last_login"])

            from apps.audit.models import AuditLog
            from apps.audit.services import log_action

            log_action(
                action=AuditLog.Action.USER_LOGIN,
                actor=user,
                target_type="User",
                target_id=str(user.id),
                description=f"User {user.username} verified MFA and signed in successfully",
                ip_address=get_client_ip(request),
            )

            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "mfa_required": False,
                "user": UserProfileSerializer(profile).data,
            })



        # Step 1: Validate username and password.

        username = str(request.data.get("username", "")).strip()

        password = str(request.data.get("password", ""))



        user = authenticate(

            request=request,

            username=username,

            password=password,

        )



        # Allow sign-in by case-insensitive username or email
        if user is None:
            username_candidate = User.objects.filter(username__iexact=username).first()
            user_candidate = username_candidate or User.objects.filter(email__iexact=username).first()
            # Django's authenticate() already checked a real username and
            # emitted user_login_failed; do not repeat an expensive hash check.
            if not username_candidate and user_candidate and user_candidate.check_password(password):
                user = user_candidate



        if user is None or not user.is_active:

            return Response(

                {"detail": "Invalid username or password."},

                status=status.HTTP_401_UNAUTHORIZED,

            )



        profile = get_or_sync_profile(user)

        if not profile.email_verified:
            return Response(
                {
                    "detail": "Verify your email address before signing in.",
                    "email_verification_required": True,
                },
                status=status.HTTP_403_FORBIDDEN,
            )



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



        # If user does NOT have MFA enabled, require MFA setup enrollment before dashboard access
        secret = profile.pending_totp_secret
        if not secret:
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
                "Scan the QR code with Google Authenticator or "
                "Microsoft Authenticator, then enter the six-digit code to complete setup and sign in."
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

                logger.warning("MFA recovery email configuration failed (%s)", type(e).__name__)

                return Response(

                    {"detail": "Unable to dispatch email due to mail server configuration error."},

                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,

                )

            except EmailDeliveryError as e:

                logger.error("MFA recovery email delivery failed (%s)", type(e).__name__)

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



    @transaction.atomic
    def post(self, request):

        token_str = str(request.data.get("token", "")).strip()

        if not token_str:

            return Response(

                {"detail": "Recovery token is required."},

                status=status.HTTP_400_BAD_REQUEST,

            )



        token_hash = hashlib.sha256(token_str.encode("utf-8")).hexdigest()

        recovery_record = (

            MFARecoveryToken.objects.select_for_update().filter(
                token_hash=token_hash,
                purpose="mfa_recovery",
            )

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

        if recovery_record.user.profile.pending_totp_secret:
            return Response(
                {"detail": "Authenticator setup is already in progress. Complete it with the displayed code."},
                status=status.HTTP_409_CONFLICT,
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



    @transaction.atomic
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

        except (TokenError, KeyError, TypeError, ValueError, User.DoesNotExist):

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

        recovery_record = MFARecoveryToken.objects.select_for_update().filter(

            id=recovery_token_id,

            user=user,

        ).first()



        if not recovery_record or not recovery_record.is_valid():

            return Response(

                {"detail": "Recovery session is expired or already used."},

                status=status.HTTP_400_BAD_REQUEST,

            )



        profile = get_or_sync_profile(user)

        profile = UserProfile.objects.select_for_update().get(pk=profile.pk)

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

        # Deliver after the token/profile transaction commits so SMTP latency
        # cannot hold the locked recovery rows or profile open.
        def send_recovery_notice():
            try:
                send_mfa_reset_notification_email(user)
            except Exception as exc:
                logger.warning("MFA recovery notification failed (%s)", type(exc).__name__)

        transaction.on_commit(send_recovery_notice)



        # Issue tokens for API compatibility; frontend guides user to Back to Sign In

        refresh = issue_user_refresh_token(user)
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])



        return Response({

            "refresh": str(refresh),

            "access": str(refresh.access_token),

            "detail": "MFA recovery complete. Your new authenticator has been enrolled and activated. Please sign in to continue.",

            "success": True,

        })





class PasswordResetRequestView(APIView):
    """Send a generic response and a hashed, single-use reset-link token."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetIPThrottle]

    @transaction.atomic
    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        if not email or "@" not in email:
            return Response({"detail": "Enter a valid email address."}, status=status.HTTP_400_BAD_REQUEST)

        generic = (
            "If an account with that email address exists, "
            "a password reset link has been sent to your email address."
        )
        matches = User.objects.filter(email__iexact=email, is_active=True)
        if matches.count() != 1:
            return Response({"detail": generic}, status=status.HTTP_200_OK)

        user_id = matches.values_list("pk", flat=True).first()
        user = User.objects.select_for_update().get(pk=user_id)
        recent = PasswordResetToken.objects.filter(
            user=user,
            purpose="password_reset",
            created_at__gte=timezone.now() - timedelta(hours=1),
        )
        if recent.filter(created_at__gte=timezone.now() - timedelta(seconds=60)).exists() or recent.count() >= 5:
            return Response({"detail": generic}, status=status.HTTP_200_OK)

        PasswordResetToken.objects.filter(
            user=user, purpose="password_reset", is_used=False
        ).update(
            is_used=True, used_at=timezone.now()
        )
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        reset_record = PasswordResetToken.objects.create(
            user=user,
            token_hash=token_hash,
            expires_at=timezone.now() + timedelta(minutes=15),
            purpose="password_reset",
        )
        frontend_base = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
        # Fragment values are not sent to the frontend host or included in HTTP
        # access logs and Referer headers. The page immediately removes it.
        reset_url = f"{frontend_base}/reset-password#token={raw_token}"
        try:
            send_password_reset_email(user, reset_url)
        except (SMTPConfigurationError, EmailDeliveryError) as exc:
            reset_record.is_used = True
            reset_record.used_at = timezone.now()
            reset_record.save(update_fields=["is_used", "used_at"])
            logger.warning("Password reset email delivery failed (%s).", type(exc).__name__)
        return Response({"detail": generic}, status=status.HTTP_200_OK)


class PasswordResetValidateTokenView(APIView):
    """Validate only the secure reset-link token contract."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetIPThrottle]

    def _validate_token_str(self, token_str):
        if not token_str:
            return Response(
                {"detail": "Password reset token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        token_hash = hashlib.sha256(token_str.encode("utf-8")).hexdigest()
        record = (
            PasswordResetToken.objects.filter(
                token_hash=token_hash,
                purpose="password_reset",
                is_used=False,
            )
            .select_related("user")
            .first()
        )
        if record and record.is_valid() and record.user.is_active:
            return Response(
                {
                    "valid": True,
                    "email": record.user.email,
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
        token = str(request.data.get("token") or request.data.get("reset_token") or "").strip()
        return self._validate_token_str(token)

    def get(self, request):
        token = str(request.query_params.get("token") or request.query_params.get("reset_token") or "").strip()
        return self._validate_token_str(token)


class PasswordResetCompleteView(APIView):
    """Consume a secure email-link token exactly once and invalidate old sessions."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetIPThrottle]

    def post(self, request):
        raw_token = str(request.data.get("token") or request.data.get("reset_token") or "").strip()
        password = str(request.data.get("password", ""))
        password_confirm = str(request.data.get("password_confirm", ""))
        if not raw_token:
            return Response({"detail": "Password reset authorization token is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not password:
            return Response({"password": ["Password is required."]}, status=status.HTTP_400_BAD_REQUEST)
        if password != password_confirm:
            return Response({"password_confirm": ["Passwords do not match."]}, status=status.HTTP_400_BAD_REQUEST)

        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        try:
            with transaction.atomic():
                token_record = PasswordResetToken.objects.select_for_update().select_related("user").get(
                    token_hash=token_hash, purpose="password_reset", is_used=False
                )
                if not token_record.is_valid() or not token_record.user.is_active:
                    raise PasswordResetToken.DoesNotExist
                user = User.objects.select_for_update().get(pk=token_record.user_id)
                try:
                    validate_password(password, user=user)
                except DjangoValidationError as exc:
                    return Response({"password": list(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

                now = timezone.now()
                user.set_password(password)
                user.save(update_fields=["password"])
                profile = get_or_sync_profile(user)
                profile.password_changed_at = now
                profile.save(update_fields=["password_changed_at", "updated_at"])

                token_record.is_used = True
                token_record.used_at = now
                token_record.save(update_fields=["is_used", "used_at"])
                PasswordResetToken.objects.filter(user=user, is_used=False).update(
                    is_used=True, used_at=now
                )
                PasswordResetRequest.objects.filter(user=user, is_completed=False).update(
                    is_completed=True
                )
        except (PasswordResetToken.DoesNotExist, User.DoesNotExist):
            return Response(
                {"detail": "This password reset session is invalid, expired, or already used. Please request a new reset link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            send_password_changed_notification_email(user)
        except Exception as exc:
            logger.warning("Password-change notification failed (%s).", type(exc).__name__)
        try:
            from apps.audit.models import AuditLog
            from apps.audit.services import log_action
            log_action(
                action=AuditLog.Action.OTHER,
                actor=user,
                target_type="User",
                target_id=str(user.pk),
                description="Password reset completed through email verification",
                ip_address=get_client_ip(request),
            )
        except Exception:
            logger.exception("Password reset completed but its audit event could not be recorded")
        return Response({
            "detail": "Your password has been changed successfully. Please sign in with your new password."
        }, status=status.HTTP_200_OK)


class VerifyEmailView(APIView):

    """

    Verify a user's email address using 6-digit OTP or link token.

    Once email is verified, immediately triggers auto-claiming of any

    unclaimed certificates associated with this email.

    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [EmailVerificationIPThrottle]



    @transaction.atomic
    def post(self, request):

        email = str(request.data.get("email", "")).strip().lower()

        otp = str(request.data.get("otp", "")).strip()

        token = str(request.data.get("token", "")).strip()



        if not otp and not token:

            return Response(

                {"detail": "Verification code (OTP) or token is required."},

                status=status.HTTP_400_BAD_REQUEST,

            )



        now = timezone.now()

        token_record = None

        user = None



        if request.user and request.user.is_authenticated:

            user = request.user

        elif email:

            user = User.objects.filter(email__iexact=email).first()



        # If user is still None and a token was provided, look up by token hash directly

        if not user and token:

            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

            token_record = EmailVerificationToken.objects.filter(

                token_hash=token_hash,

                is_used=False,

                expires_at__gt=now,

                attempts__lt=5,

            ).select_for_update().select_related("user").first()

            if token_record:

                user = token_record.user



        if not user:

            return Response(

                {"detail": "User not found or email required."},

                status=status.HTTP_400_BAD_REQUEST,

            )



        EmailVerificationToken.objects.filter(
            user=user, is_used=False, expires_at__lte=now
        ).update(is_used=True, used_at=now)

        profile = get_or_sync_profile(user)



        # If token_record was not resolved yet, search active tokens for this user

        if not token_record:

            active_tokens = EmailVerificationToken.objects.filter(

                user=user,

                is_used=False,

                expires_at__gt=now,

                attempts__lt=5,

            ).select_for_update().order_by("-created_at", "-id")



            if otp:

                otp_hash = hashlib.sha256(otp.encode("utf-8")).hexdigest()

                token_record = active_tokens.filter(otp_hash=otp_hash).first()

            elif token:

                token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

                token_record = active_tokens.filter(token_hash=token_hash).first()

            if not token_record:
                failed_record = active_tokens.first()
                if failed_record:
                    failed_record.attempts += 1
                    update_fields = ["attempts"]
                    if failed_record.attempts >= 5:
                        failed_record.is_used = True
                        failed_record.used_at = now
                        update_fields.extend(["is_used", "used_at"])
                    failed_record.save(update_fields=update_fields)



        if not token_record:

            return Response(

                {"detail": "Invalid or expired verification code."},

                status=status.HTTP_400_BAD_REQUEST,

            )



        # Mark token as used

        token_record.is_used = True

        token_record.used_at = now

        token_record.save(update_fields=["is_used", "used_at"])



        # Invalidate any other pending verification tokens for this user

        EmailVerificationToken.objects.filter(

            user=user,

            is_used=False,

        ).update(is_used=True, used_at=now)



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
    authentication_classes = []
    throttle_classes = [EmailVerificationIPThrottle]



    @transaction.atomic
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

                {"detail": "If verification is required, instructions will be sent to the matching email."},

                status=status.HTTP_200_OK,

            )

        user = User.objects.select_for_update().get(pk=user.pk)



        profile = get_or_sync_profile(user)

        if profile.email_verified:

            return Response(

                {"detail": "If verification is required, instructions will be sent to the matching email."},

                status=status.HTTP_200_OK,

            )

        # Rate limit: check if a token was created in the last 60 seconds

        recent_token = EmailVerificationToken.objects.filter(

            user=user,

            is_used=False,

            created_at__gte=timezone.now() - timedelta(seconds=60),

        ).first()

        if recent_token:

            return Response(

                {"detail": "If verification is required, instructions will be sent to the matching email."},

                status=status.HTTP_200_OK,

            )

        recent_count = EmailVerificationToken.objects.filter(
            user=user,
            created_at__gte=timezone.now() - timedelta(hours=1),
        ).count()
        if recent_count >= 5:
            return Response(
                {"detail": "If verification is required, instructions will be sent to the matching email."},
                status=status.HTTP_200_OK,
            )



        # Invalidate previous unused tokens

        EmailVerificationToken.objects.filter(
            user=user,
            is_used=False,
            expires_at__lte=timezone.now(),
        ).update(is_used=True, used_at=timezone.now())

        EmailVerificationToken.objects.filter(user=user, is_used=False).update(

            is_used=True, used_at=timezone.now()

        )



        otp = f"{secrets.randbelow(1_000_000):06d}"

        otp_hash = hashlib.sha256(otp.encode("utf-8")).hexdigest()

        token = secrets.token_urlsafe(32)

        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()



        verification_record = EmailVerificationToken.objects.create(

            user=user,

            token_hash=token_hash,

            otp_hash=otp_hash,

            expires_at=timezone.now() + timedelta(minutes=10),

        )



        try:

            email_sent = bool(send_email_verification_otp_email(user, otp))

        except Exception as e:

            logger.warning("Failed to resend verification email (%s)", type(e).__name__)

            email_sent = False


        if not email_sent:

            verification_record.is_used = True

            verification_record.used_at = timezone.now()

            verification_record.save(update_fields=["is_used", "used_at"])

            return Response(

                {"detail": "Verification email could not be sent. Please try again shortly."},

                status=status.HTTP_503_SERVICE_UNAVAILABLE,

            )



        return Response(

            {"detail": "Verification code has been sent to your email."},

            status=status.HTTP_200_OK,

        )





class GoogleAuthView(APIView):

    """

    POST /api/accounts/google-login/

    Authenticates a user via verified Google OAuth ID token.

    Returns JWTs only when the account's required factors are complete. Accounts

    with enrolled TOTP receive a challenge; password-bearing accounts that have

    not enrolled MFA must complete setup through password sign-in first.

    """

    permission_classes = [AllowAny]

    authentication_classes = []

    throttle_classes = [LoginIPThrottle, LoginIdentityThrottle]



    def post(self, request):

        raw_token = (
            request.data.get("id_token")
            or request.data.get("credential")
            or request.data.get("token")
            or ""
        )
        token_str = raw_token.strip() if isinstance(raw_token, str) else ""



        if not token_str:

            return Response(

                {"detail": "Google ID token (credential) is required."},

                status=status.HTTP_400_BAD_REQUEST,

            )



        client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")

        if not client_id:
            logger.error("Google Sign-In requested without GOOGLE_OAUTH_CLIENT_ID")
            return Response(
                {"detail": "Google Sign-In is not configured on this server."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )



        from google.oauth2 import id_token

        from google.auth.transport import requests as google_requests



        try:

            request_adapter = google_requests.Request()

            id_info = id_token.verify_oauth2_token(
                token_str,
                request_adapter,
                audience=client_id,
            )



            # Validate issuer

            if id_info.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:

                return Response(

                    {"detail": "Invalid Google token issuer."},

                    status=status.HTTP_401_UNAUTHORIZED,

                )



            # Validate email and verification

            email = (id_info.get("email") or "").strip().lower()

            if not email:

                return Response(

                    {"detail": "Google token does not contain an email address."},

                    status=status.HTTP_400_BAD_REQUEST,

                )



            email_verified = id_info.get("email_verified", False)

            if email_verified is not True:

                return Response(

                    {"detail": "Google email address is not verified by Google."},

                    status=status.HTTP_401_UNAUTHORIZED,

                )



        except ValueError as exc:

            logger.warning("Google token validation failed: %s", exc)

            return Response(

                {"detail": "Invalid or expired Google authentication token."},

                status=status.HTTP_401_UNAUTHORIZED,

            )

        except Exception as exc:

            logger.exception("Error verifying Google OAuth token: %s", exc)

            return Response(

                {"detail": "Authentication with Google failed. Please try again."},

                status=status.HTTP_400_BAD_REQUEST,

            )



        # Token verified! Find or create local user account
        google_sub = str(id_info.get("sub") or "").strip()
        if not google_sub:
            return Response(
                {"detail": "Google ID token does not contain a subject identifier."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Step 1: Look up by stable Google subject identifier first
        user = None
        if google_sub:
            matched_profile = UserProfile.objects.filter(google_sub=google_sub).select_related("user").first()
            if matched_profile:
                user = matched_profile.user
                if not user.is_active:
                    return Response(
                        {"detail": "This account is inactive. Contact an administrator for assistance."},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )
                if (user.email or "").strip().lower() != email:
                    email_owner = User.objects.annotate(
                        normalized_email=Lower(Trim("email")),
                    ).filter(normalized_email=email).exclude(pk=user.pk).exists()
                    if email_owner:
                        return Response(
                            {"detail": "The new Google email is already linked to another account."},
                            status=status.HTTP_409_CONFLICT,
                        )
                    user.email = email
                    user.save(update_fields=["email"])

        # Step 2: If not found by sub, check for existing user by verified Google email address
        if user is None:
            existing_user = User.objects.annotate(
                normalized_email=Lower(Trim("email")),
            ).filter(normalized_email=email).first()
            if existing_user:
                if not existing_user.is_active:
                    return Response(
                        {"detail": "This account is inactive. Contact an administrator for assistance."},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )
                existing_profile = get_or_sync_profile(existing_user)
                # The Google ID token was verified for the configured client
                # and carries Google's verified-email claim. This proves
                # control of this exact address without trusting a string match.
                if existing_profile.google_sub and existing_profile.google_sub != google_sub:
                    return Response(
                        {
                            "detail": "This account is already linked to a different Google identity."
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

                # Link repeatably to the same account and preserve its user ID,
                # password, role, permissions, and certificate relationships.
                user = existing_user
                try:
                    with transaction.atomic():
                        existing_profile = UserProfile.objects.select_for_update().get(pk=existing_profile.pk)
                        if existing_profile.google_sub and existing_profile.google_sub != google_sub:
                            return Response(
                                {"detail": "This account is already linked to a different Google identity."},
                                status=status.HTTP_409_CONFLICT,
                            )
                        fields_to_update = []
                        if existing_profile.google_sub != google_sub:
                            existing_profile.google_sub = google_sub
                            fields_to_update.append("google_sub")
                        if not existing_profile.email_verified:
                            existing_profile.email_verified = True
                            existing_profile.email_verified_at = timezone.now()
                            fields_to_update.extend(["email_verified", "email_verified_at"])
                        if fields_to_update:
                            existing_profile.save(update_fields=[*fields_to_update, "updated_at"])
                except IntegrityError:
                    return Response(
                        {"detail": "This Google identity is already linked to another account."},
                        status=status.HTTP_409_CONFLICT,
                    )

        # Step 3: Create new user if not found
        if user is None:
            raw_local_part = (email.split("@", 1)[0] or "google_user").replace("+", "_").replace(".", "_")
            base_username = re.sub(r"[^\w.@+-]", "_", raw_local_part, flags=re.UNICODE) or "google_user"
            candidate_username = base_username[:25]
            counter = 1
            first_name = (id_info.get("given_name") or "").strip()[:150]
            last_name = (id_info.get("family_name") or "").strip()[:150]
            while True:
                try:
                    with transaction.atomic():
                        user = User(
                            username=candidate_username,
                            email=email,
                            first_name=first_name,
                            last_name=last_name,
                            is_active=True,
                        )
                        user.set_unusable_password()
                        user.save(force_insert=True)
                    break
                except IntegrityError:
                    if User.objects.filter(email__iexact=email).exists():
                        return Response(
                            {"detail": "An account with this Google email already exists. Sign in with that account."},
                            status=status.HTTP_409_CONFLICT,
                        )
                    if not User.objects.filter(username__iexact=candidate_username).exists():
                        raise
                    candidate_username = f"{base_username[:20]}_{counter}"
                    counter += 1

        # Update profile: ensure email_verified is True and google_sub is recorded
        try:
            with transaction.atomic():
                profile = get_or_sync_profile(user)
                profile_dirty = False
                if not profile.email_verified:
                    profile.email_verified = True
                    profile.email_verified_at = timezone.now()
                    profile_dirty = True
                if google_sub and profile.google_sub != google_sub:
                    profile.google_sub = google_sub
                    profile_dirty = True
                if profile_dirty:
                    profile.save()
        except IntegrityError:
            return Response(
                {"detail": "This Google identity is already linked to another account."},
                status=status.HTTP_409_CONFLICT,
            )

        # Link any unclaimed certificates previously issued to this email address
        try:
            from apps.certificates.services import claim_unclaimed_certificates_for_user
            claim_unclaimed_certificates_for_user(user)
        except Exception as e:
            logger.warning("Certificate claim failed during Google sign-in (%s)", type(e).__name__)

        # Respect an account's configured second factor for Google sign-in too.
        if profile.mfa_enabled and profile.totp_secret:
            challenge_token = MFAChallengeToken()
            challenge_token[api_settings.USER_ID_CLAIM] = getattr(
                user, api_settings.USER_ID_FIELD
            )
            challenge_token["purpose"] = "mfa_challenge"
            return Response({
                "mfa_required": True,
                "mfa_setup_required": False,
                "challenge": str(challenge_token),
                "detail": "Enter your authenticator code to complete Google sign-in.",
            }, status=status.HTTP_200_OK)

        # Accounts without an enrolled second factor must complete the same
        # mandatory TOTP enrollment used by password login.
        if user.has_usable_password() and not profile.mfa_enabled:
            return Response({
                "mfa_required": True,
                "mfa_setup_required": True,
                "challenge": "",
                "detail": "Sign in with your password to complete two-factor setup.",
            }, status=status.HTTP_403_FORBIDDEN)

        # Issue tokens only after all required authentication factors succeed.
        refresh = issue_user_refresh_token(user)
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        from apps.audit.models import AuditLog
        from apps.audit.services import log_action

        log_action(
            action=AuditLog.Action.USER_LOGIN,
            actor=user,
            target_type="User",
            target_id=str(user.id),
            description=f"User {user.username} signed in via trusted Google OAuth",
            ip_address=get_client_ip(request),
        )

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "mfa_required": False,
            "user": UserProfileSerializer(profile).data,
        }, status=status.HTTP_200_OK)


class SetManualPasswordView(APIView):
    """
    POST /api/accounts/set-password/
    Allows an authenticated user (e.g. Google OAuth account) to establish a secure
    manual password for subsequent username/email + password login.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        profile = get_or_sync_profile(user)

        # Only Google-authenticated accounts can set up a manual password
        if not profile.google_sub:
            return Response(
                {
                    "detail": "Manual password setup is only available for Google-authenticated accounts."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Disallow silently overwriting an existing usable local password
        if user.has_usable_password():
            return Response(
                {
                    "detail": (
                        "A manual password is already configured for this account. "
                        "Please use the password reset flow to change your password."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        password = str(request.data.get("password", ""))
        password_confirm = str(request.data.get("password_confirm", ""))

        if not password:
            return Response(
                {"detail": "New password is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if password != password_confirm:
            return Response(
                {"detail": "Passwords do not match."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(password, user=user)
        except DjangoValidationError as exc:
            msgs = exc.messages if hasattr(exc, "messages") else [str(exc)]
            return Response(
                {"detail": " ".join(msgs)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(password)
        user.save(update_fields=["password"])
        from apps.audit.models import AuditLog
        from apps.audit.services import log_action

        log_action(
            action=AuditLog.Action.OTHER,
            actor=user,
            target_type="User",
            target_id=str(user.id),
            description=f"User {user.username} established a manual password",
            ip_address=get_client_ip(request),
        )

        try:
            send_password_changed_notification_email(user)
        except Exception:
            logger.exception("Failed to send password-established notification email")

        return Response({
            "detail": "Manual password set successfully. You can now sign in using your username or email and password.",
            "user": UserProfileSerializer(profile).data,
        }, status=status.HTTP_200_OK)
