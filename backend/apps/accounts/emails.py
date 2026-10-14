"""
Email utilities for accounts app.
Delegates to the centralized apps.accounts.services.email_service to ensure all
password-reset, MFA recovery, and security notifications use a single unified implementation.
"""

from apps.accounts.services.email_service import (
    EmailDeliveryError,
    SMTPConfigurationError,
    is_smtp_configured,
    send_account_email,
    send_password_reset_email,
    send_mfa_recovery_email,
    send_password_changed_notification_email,
    send_mfa_reset_notification_email,
    send_password_reset_otp_email,
    send_email_verification_otp_email,
)

__all__ = [
    "EmailDeliveryError",
    "SMTPConfigurationError",
    "is_smtp_configured",
    "send_account_email",
    "send_password_reset_email",
    "send_mfa_recovery_email",
    "send_password_changed_notification_email",
    "send_mfa_reset_notification_email",
    "send_password_reset_otp_email",
    "send_email_verification_otp_email",
]
