"""
Centralized, secure SMTP email service for OneSmarter-CertiVerify.

All password-reset, MFA recovery, and account security notifications flow through
this service. Reads SMTP configuration exclusively from backend settings/environment,
never accepts credentials or recipient overrides from client input, and ensures
credentials/tokens are never printed to logs.
"""

import logging
import smtplib
import socket
from typing import Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """Raised when an email cannot be sent via the configured mail backend."""
    pass


class SMTPConfigurationError(EmailDeliveryError):
    """Raised when the SMTP backend is active but credentials or host are missing."""
    pass


def is_smtp_configured() -> tuple[bool, str]:
    """
    Check whether SMTP is fully configured when using SMTP backend.
    Returns (is_configured: bool, reason: str).
    """
    backend = getattr(settings, "EMAIL_BACKEND", "")
    if "smtp.EmailBackend" in backend:
        host = getattr(settings, "EMAIL_HOST", "").strip()
        user = getattr(settings, "EMAIL_HOST_USER", "").strip()
        pwd = getattr(settings, "EMAIL_HOST_PASSWORD", "").strip()
        if not host:
            return False, "EMAIL_HOST is not configured in environment variables."
        if not user or not pwd or pwd == "REPLACE_WITH_A_NEW_VALID_SMTP_PASSWORD":
            return False, (
                "SMTP email backend is active but EMAIL_HOST_USER or EMAIL_HOST_PASSWORD "
                "is not configured with valid credentials in backend/.env."
            )
    return True, ""


def send_account_email(
    recipient_email: str,
    subject: str,
    message: str,
    html_message: Optional[str] = None,
    reply_to: Optional[str] = None,
) -> bool:
    """
    Send an email safely through Django's configured email backend.

    Guarantees:
    1. Credentials/passwords are NEVER logged.
    2. Uses DEFAULT_FROM_EMAIL and centrally configured reply-to address.
    3. Supports HTML with plain-text fallback.
    4. Handles connection timeouts, authentication failures, and delivery rejections cleanly.
    """
    clean_recipient = (recipient_email or "").strip()
    if not clean_recipient or "@" not in clean_recipient:
        raise EmailDeliveryError("A valid recipient email address is required.")

    configured, error_reason = is_smtp_configured()
    if not configured:
        logger.warning("Email dispatch to %s blocked: %s", clean_recipient, error_reason)
        raise SMTPConfigurationError(error_reason)

    from_email = getattr(
        settings,
        "DEFAULT_FROM_EMAIL",
        "OneSmarter Support <support@onesmarter.com>",
    )
    reply_to_email = reply_to or getattr(settings, "EMAIL_REPLY_TO", "help@onesmarter.com")

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=message,
            from_email=from_email,
            to=[clean_recipient],
            reply_to=[reply_to_email],
        )

        if html_message:
            msg.attach_alternative(html_message, "text/html")

        sent_count = msg.send(fail_silently=False)
        if sent_count < 1:
            logger.error("SMTP server rejected delivery for recipient: %s", clean_recipient)
            raise EmailDeliveryError("Mail server did not accept the message for delivery.")

        logger.info("Email '%s' accepted by SMTP server for recipient: %s", subject, clean_recipient)
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error(
            "SMTP authentication failure sending to %s (code %s): %s",
            clean_recipient,
            getattr(e, "smtp_code", "unknown"),
            getattr(e, "smtp_error", "Authentication failed"),
        )
        raise EmailDeliveryError("SMTP authentication failed. Verify EMAIL_HOST_USER and EMAIL_HOST_PASSWORD.")
    except smtplib.SMTPConnectError as e:
        logger.error("SMTP connection error sending to %s: %s", clean_recipient, e)
        raise EmailDeliveryError("Failed to connect to SMTP server. Verify EMAIL_HOST and EMAIL_PORT.")
    except socket.timeout:
        logger.error("SMTP timeout connecting to mail server for %s", clean_recipient)
        raise EmailDeliveryError("SMTP connection timed out. Check network connection and EMAIL_TIMEOUT.")
    except smtplib.SMTPException as e:
        logger.error("SMTP protocol error sending to %s: %s", clean_recipient, e)
        raise EmailDeliveryError(f"SMTP server error: {e}")
    except Exception as e:
        logger.error(
            "Unexpected email delivery failure for %s: %s: %s",
            clean_recipient,
            type(e).__name__,
            e,
        )
        raise EmailDeliveryError("Email delivery failed due to a server error.")


# -----------------------------------------------------------------------------
# HTML Template Builder (Branded OneSmarter Identity)
# -----------------------------------------------------------------------------

def _render_email_html(title: str, greeting: str, content_html: str, action_button: Optional[dict] = None) -> str:
    """
    Renders a responsive, clean, branded HTML email consistent with OneSmarter-CertiVerify.
    Colors match the teal (#0d9488) and dark slate (#0f172a) palette of the website.
    """
    btn_html = ""
    if action_button and action_button.get("url") and action_button.get("label"):
        btn_html = f"""
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="margin: 28px 0 24px 0;">
          <tr>
            <td align="left">
              <a href="{action_button['url']}" target="_blank" style="display: inline-block; padding: 14px 28px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 15px; font-weight: 600; color: #ffffff; text-decoration: none; background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%); border-radius: 10px; box-shadow: 0 4px 12px rgba(13, 148, 136, 0.25);">
                {action_button['label']} &rarr;
              </a>
            </td>
          </tr>
        </table>
        <p style="margin: 0 0 16px 0; font-size: 12px; color: #64748b; line-height: 1.5;">
          If the button above does not work, copy and paste this URL into your browser:<br>
          <a href="{action_button['url']}" style="color: #0d9488; word-break: break-all;">{action_button['url']}</a>
        </p>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; -webkit-font-smoothing: antialiased;">
  <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f1f5f9; padding: 32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 580px; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01); border: 1px solid #e2e8f0;">
          <!-- Header -->
          <tr>
            <td style="padding: 28px 36px; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); border-bottom: 3px solid #0d9488;">
              <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                <tr>
                  <td>
                    <span style="font-size: 20px; font-weight: 700; color: #ffffff; letter-spacing: -0.5px;">OneSmarter</span>
                    <span style="font-size: 20px; font-weight: 400; color: #14b8a6; margin-left: 4px;">CertiVerify</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Body Content -->
          <tr>
            <td style="padding: 36px 36px 28px 36px;">
              <h1 style="margin: 0 0 16px 0; font-size: 20px; font-weight: 700; color: #0f172a; line-height: 1.3;">
                {title}
              </h1>
              <p style="margin: 0 0 18px 0; font-size: 15px; color: #334155; line-height: 1.6;">
                {greeting}
              </p>
              <div style="font-size: 14px; color: #334155; line-height: 1.6;">
                {content_html}
              </div>
              {btn_html}
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding: 24px 36px; background-color: #f8fafc; border-top: 1px solid #e2e8f0; font-size: 12px; color: #64748b; line-height: 1.6;">
              <p style="margin: 0 0 6px 0; font-weight: 600; color: #475569;">OneSmarter-CertiVerify Support</p>
              <p style="margin: 0 0 8px 0;">Need assistance? Contact us at <a href="mailto:support@onesmarter.com" style="color: #0d9488; text-decoration: none;">support@onesmarter.com</a> or <a href="mailto:help@onesmarter.com" style="color: #0d9488; text-decoration: none;">help@onesmarter.com</a>.</p>
              <p style="margin: 0; color: #94a3b8; font-size: 11px;">&copy; OneSmarter, Inc. All rights reserved. Automated security notification.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# -----------------------------------------------------------------------------
# Specific Account Workflow Emails
# -----------------------------------------------------------------------------

def send_password_reset_email(user, reset_url: str) -> bool:
    """
    Send secure password reset link to user.
    Token expires in 15 minutes and can only be used once.
    """
    name = (getattr(user, "first_name", "") or getattr(user, "username", "")).strip() or "User"
    subject = "Reset Your OneSmarter-CertiVerify Password"

    plain_text = (
        f"Hello {name},\n\n"
        "We received a request to reset your OneSmarter-CertiVerify account password.\n\n"
        "To choose a new password, click the link below:\n\n"
        f"{reset_url}\n\n"
        "This secure link expires after 15 minutes and can only be used once.\n\n"
        "If you did not request this change, ignore this email. Your current password will remain unchanged.\n\n"
        "Regards,\n"
        "OneSmarter Support\n"
        "support@onesmarter.com | help@onesmarter.com\n"
    )

    content_html = """
      <p style="margin: 0 0 14px 0;">We received a request to reset your OneSmarter-CertiVerify account password.</p>
      <p style="margin: 0 0 14px 0;">To choose a new password, click the button below to open the secure reset page:</p>
      <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 12px 16px; margin: 18px 0; font-size: 13px; color: #166534;">
        <strong>Notice:</strong> This secure link expires after <strong>15 minutes</strong> and can only be used once.
      </div>
      <p style="margin: 0 0 8px 0; font-size: 13px; color: #64748b;">
        If you did not request this change, please ignore this email. Your current password will remain unchanged and your account stays secure.
      </p>
    """

    html = _render_email_html(
        title="Reset Your Password",
        greeting=f"Hello {name},",
        content_html=content_html,
        action_button={"label": "Reset Password", "url": reset_url},
    )

    return send_account_email(user.email, subject, plain_text, html)


def send_mfa_recovery_email(user, recovery_url: str) -> bool:
    """
    Send MFA reauthorization/recovery link to user.
    Token expires in 15 minutes and is strictly single-use.
    """
    name = (getattr(user, "first_name", "") or getattr(user, "username", "")).strip() or "User"
    subject = "OneSmarter-CertiVerify MFA Reauthorization Request"

    plain_text = (
        f"Hello {name},\n\n"
        "A request was received to reauthorize multi-factor authentication for your OneSmarter-CertiVerify account.\n\n"
        "If you initiated this request, use the secure link below to continue the MFA recovery process:\n\n"
        f"{recovery_url}\n\n"
        "This link expires after 15 minutes and can only be used once.\n\n"
        "After the link is verified, you will be guided through setting up a new authenticator using Google Authenticator "
        "or Microsoft Authenticator. You must confirm the new authenticator with a valid OTP before the new enrollment becomes active.\n\n"
        "If you did not request this change, do not use the link. Contact OneSmarter Support if you suspect unauthorized activity.\n\n"
        "Regards,\n"
        "OneSmarter Support\n"
        "support@onesmarter.com | help@onesmarter.com\n"
    )

    content_html = """
      <p style="margin: 0 0 14px 0;">A request was received to reauthorize multi-factor authentication for your OneSmarter-CertiVerify account.</p>
      <p style="margin: 0 0 14px 0;">If you initiated this request, click the button below to configure your new authenticator:</p>
      <div style="background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 12px 16px; margin: 18px 0; font-size: 13px; color: #1e40af;">
        <strong>How MFA Recovery Works:</strong>
        <ul style="margin: 8px 0 0 0; padding-left: 20px; font-size: 12px; line-height: 1.6;">
          <li>This link expires in <strong>15 minutes</strong> and can only be used once.</li>
          <li>You will be guided to scan a new QR code using <strong>Google Authenticator</strong> or <strong>Microsoft Authenticator</strong>.</li>
          <li>You must confirm the new authenticator with a valid 6-digit OTP before enrollment is activated.</li>
        </ul>
      </div>
      <p style="margin: 0 0 8px 0; font-size: 13px; color: #b91c1c; font-weight: 500;">
        If you did not request this change, do not use the link. Contact OneSmarter Support immediately if you suspect unauthorized activity.
      </p>
    """

    html = _render_email_html(
        title="MFA Reauthorization Request",
        greeting=f"Hello {name},",
        content_html=content_html,
        action_button={"label": "Reauthorize MFA", "url": recovery_url},
    )

    return send_account_email(user.email, subject, plain_text, html)


def send_password_changed_notification_email(user) -> bool:
    """Send security notification confirming password change."""
    name = (getattr(user, "first_name", "") or getattr(user, "username", "")).strip() or "User"
    subject = "OneSmarter-CertiVerify — Your Password Has Been Changed"

    plain_text = (
        f"Hello {name},\n\n"
        "The password for your OneSmarter-CertiVerify account was successfully changed.\n\n"
        "If you made this change, no further action is required.\n\n"
        "If you did NOT make this change, please contact OneSmarter Support immediately at support@onesmarter.com "
        "or help@onesmarter.com to secure your account.\n\n"
        "Regards,\n"
        "OneSmarter Support\n"
    )

    content_html = """
      <p style="margin: 0 0 14px 0;">The password for your OneSmarter-CertiVerify account was successfully updated.</p>
      <p style="margin: 0 0 14px 0;">If you performed this update, no further action is required.</p>
      <div style="background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 12px 16px; margin: 18px 0; font-size: 13px; color: #991b1b;">
        <strong>Security Advisory:</strong> If you did NOT change your password, your account may be compromised.
        Please contact OneSmarter Support immediately at <a href="mailto:support@onesmarter.com" style="color: #991b1b; font-weight: 600;">support@onesmarter.com</a>.
      </div>
    """

    html = _render_email_html(
        title="Password Updated Successfully",
        greeting=f"Hello {name},",
        content_html=content_html,
    )

    return send_account_email(user.email, subject, plain_text, html)


def send_mfa_reset_notification_email(user) -> bool:
    """Send notification confirming that MFA authenticator was re-enrolled."""
    name = (getattr(user, "first_name", "") or getattr(user, "username", "")).strip() or "User"
    subject = "OneSmarter CertiVerify — Two-Factor Authentication Updated"

    plain_text = (
        f"Hello {name},\n\n"
        "Two-factor authentication for your OneSmarter-CertiVerify account was successfully re-enrolled with a new authenticator app.\n\n"
        "If you made this change, you may now use your newly registered authenticator code to sign in.\n\n"
        "If you did NOT authorize this change, please contact OneSmarter Support immediately.\n\n"
        "Regards,\n"
        "OneSmarter Support\n"
    )

    content_html = """
      <p style="margin: 0 0 14px 0;">Two-factor authentication for your OneSmarter-CertiVerify account was successfully updated.</p>
      <p style="margin: 0 0 14px 0;">Your new Google Authenticator or Microsoft Authenticator app is now active for account sign-ins.</p>
      <div style="background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 12px 16px; margin: 18px 0; font-size: 13px; color: #991b1b;">
        <strong>Security Warning:</strong> If you did NOT authorize this authenticator change, please contact
        OneSmarter Support immediately at <a href="mailto:support@onesmarter.com" style="color: #991b1b; font-weight: 600;">support@onesmarter.com</a>.
      </div>
    """

    html = _render_email_html(
        title="Two-Factor Authentication Updated",
        greeting=f"Hello {name},",
        content_html=content_html,
    )

    return send_account_email(user.email, subject, plain_text, html)


def send_password_reset_otp_email(user, otp: str) -> bool:
    """Send 6-digit email OTP for password recovery (backward-compatible)."""
    name = (getattr(user, "first_name", "") or getattr(user, "username", "")).strip() or "User"
    subject = "OneSmarter CertiVerify — Password Reset Verification Code"

    plain_text = (
        f"Hello {name},\n\n"
        "A request was received to reset the password for your OneSmarter CertiVerify account.\n\n"
        f"Your 6-digit verification code is:\n\n"
        f"    {otp}\n\n"
        "This verification code is valid for 10 minutes and can only be used once.\n\n"
        "If you did not request a password reset, please ignore this email. Your current password remains secure.\n\n"
        "Regards,\n"
        "OneSmarter Support\n"
    )

    content_html = f"""
      <p style="margin: 0 0 14px 0;">A request was received to reset the password for your OneSmarter CertiVerify account.</p>
      <div style="background-color: #f8fafc; border: 2px dashed #cbd5e1; border-radius: 12px; padding: 20px; text-align: center; margin: 20px 0;">
        <span style="font-family: monospace; font-size: 32px; font-weight: 700; letter-spacing: 6px; color: #0d9488;">{otp}</span>
      </div>
      <p style="margin: 0 0 14px 0; font-size: 13px; color: #64748b;">This verification code is valid for 10 minutes and can only be used once.</p>
      <p style="margin: 0; font-size: 13px; color: #64748b;">If you did not request a password reset, you can safely ignore this email.</p>
    """

    html = _render_email_html(
        title="Password Reset Verification Code",
        greeting=f"Hello {name},",
        content_html=content_html,
    )

    return send_account_email(user.email, subject, plain_text, html)
