from django.urls import path
from .views import (
    CurrentUserView,
    RegisterView,
    MFASetupView,
    MFAConfirmView,
    MFALoginView,
    MFAVerifyView,
    MFARecoveryRequestView,
    MFARecoveryConfirmView,
    MFARecoveryCompleteView,
    PasswordResetRequestView,
    PasswordResetValidateTokenView,
    PasswordResetVerifyView,
    PasswordResetCompleteView,
    VerifyEmailView,
    ResendVerificationEmailView,
    GoogleAuthView,
    SetManualPasswordView,
)
from .serializers import ExistingUserTokenRefreshSerializer
from rest_framework_simplejwt.views import TokenRefreshView


class ExistingUserTokenRefreshView(TokenRefreshView):
    serializer_class = ExistingUserTokenRefreshSerializer
from .admin_views import AdminUserListView, AdminUserDetailView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-email/", VerifyEmailView.as_view(), name="verify_email"),
    path("resend-verification/", ResendVerificationEmailView.as_view(), name="resend_verification"),
    path("login/", MFALoginView.as_view(), name="login"),
    path("set-password/", SetManualPasswordView.as_view(), name="set_password"),
    path("google-login/", GoogleAuthView.as_view(), name="google_login"),
    path("google/", GoogleAuthView.as_view(), name="google_auth"),
    path("token/refresh/", ExistingUserTokenRefreshView.as_view(), name="token_refresh"),
    path("me/", CurrentUserView.as_view(), name="current_user"),
    path("mfa/setup/", MFASetupView.as_view(), name="mfa_setup"),
    path("mfa/confirm/", MFAConfirmView.as_view(), name="mfa_confirm"),
    path("mfa/verify/", MFAVerifyView.as_view(), name="mfa_verify"),
    # MFA Account Recovery
    path("mfa/recovery/request/", MFARecoveryRequestView.as_view(), name="mfa_recovery_request"),
    path("mfa/recovery/confirm/", MFARecoveryConfirmView.as_view(), name="mfa_recovery_confirm"),
    path("mfa/recovery/complete/", MFARecoveryCompleteView.as_view(), name="mfa_recovery_complete"),
    # Password Reset via Email Link / Token
    path("password-reset/request/", PasswordResetRequestView.as_view(), name="password_reset_request"),
    path("password-reset/validate/", PasswordResetValidateTokenView.as_view(), name="password_reset_validate"),
    path("password-reset/verify/", PasswordResetVerifyView.as_view(), name="password_reset_verify"),
    path("password-reset/complete/", PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    # Admin-only
    path("admin/users/", AdminUserListView.as_view(), name="admin-user-list"),
    path("admin/users/<int:pk>/", AdminUserDetailView.as_view(), name="admin-user-detail"),
]