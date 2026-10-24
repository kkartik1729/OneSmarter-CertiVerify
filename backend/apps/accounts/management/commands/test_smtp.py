"""
Django management command to safely test SMTP configuration, connection,
and account email workflows using the centralized OneSmarter email service.
"""

import smtplib
import socket
from unittest.mock import MagicMock
from django.utils import timezone

from django.conf import settings
from django.core.mail import get_connection
from django.core.management.base import BaseCommand

from apps.accounts.services.email_service import (
    is_smtp_configured,
    send_account_email,
    send_mfa_recovery_email,
    send_password_reset_email,
)


def mask_email(email_str: str) -> str:
    """Mask email for safe logging (e.g. a***r@onesmarter.com)."""
    if not email_str:
        return "[NOT SET]"
    parts = email_str.split("@")
    if len(parts) == 2:
        user, domain = parts
        if len(user) <= 2:
            masked_user = user[0] + "***"
        else:
            masked_user = user[0] + "***" + user[-1]
        return f"{masked_user}@{domain}"
    return email_str[:2] + "***"


class Command(BaseCommand):
    help = "Safely test central SMTP configuration, connection, and account email workflows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--recipient",
            type=str,
            help="Recipient email address to send a real test email to.",
        )
        parser.add_argument(
            "--type",
            type=str,
            choices=["diagnostic", "reset", "mfa"],
            default="diagnostic",
            help="Type of test email to send: 'diagnostic', 'reset', or 'mfa'.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=" * 65))
        self.stdout.write(self.style.NOTICE(" OneSmarter-CertiVerify — Central SMTP Diagnostic Tool"))
        self.stdout.write(self.style.NOTICE("=" * 65))

        backend = getattr(settings, "EMAIL_BACKEND", "")
        host = getattr(settings, "EMAIL_HOST", "")
        port = getattr(settings, "EMAIL_PORT", 0)
        use_tls = getattr(settings, "EMAIL_USE_TLS", False)
        use_ssl = getattr(settings, "EMAIL_USE_SSL", False)
        user = getattr(settings, "EMAIL_HOST_USER", "")
        password = getattr(settings, "EMAIL_HOST_PASSWORD", "")
        timeout = getattr(settings, "EMAIL_TIMEOUT", 20)
        default_from = getattr(settings, "DEFAULT_FROM_EMAIL", "")
        reply_to = getattr(settings, "EMAIL_REPLY_TO", "")

        self.stdout.write(f"EMAIL_BACKEND:       {backend}")
        self.stdout.write(f"EMAIL_HOST:          {host}")
        self.stdout.write(f"EMAIL_PORT:          {port}")
        self.stdout.write(f"EMAIL_USE_TLS:       {use_tls}")
        self.stdout.write(f"EMAIL_USE_SSL:       {use_ssl}")
        self.stdout.write(f"EMAIL_TIMEOUT:       {timeout}s")
        self.stdout.write(f"DEFAULT_FROM_EMAIL:  {default_from}")
        self.stdout.write(f"EMAIL_REPLY_TO:      {reply_to}")
        self.stdout.write(f"EMAIL_HOST_USER:     {mask_email(user)}")
        self.stdout.write(
            f"EMAIL_HOST_PASSWORD: {'[CONFIGURED]' if password and password != 'REPLACE_WITH_A_NEW_VALID_SMTP_PASSWORD' else '[PLACEHOLDER OR NOT SET]'}"
        )
        self.stdout.write("-" * 65)

        # 1. Validation check
        configured, reason = is_smtp_configured()
        if not configured:
            self.stdout.write(
                self.style.WARNING(
                    f"WARNING: Central SMTP check flagged: {reason}\n"
                    "To enable real email dispatch via IONOS SMTP:\n"
                    "  1. Set EMAIL_HOST and EMAIL_PORT in backend/.env according to your SMTP provider.\n"
                    "  2. Set EMAIL_HOST_USER in backend/.env to the authorized sender account.\n"
                    "  3. Set EMAIL_HOST_PASSWORD to your active IONOS account password in backend/.env."
                )
            )

        # 2. Connection handshake test
        self.stdout.write(f"Testing TCP connection and SMTP handshake with {host}:{port}...")
        try:
            connection = get_connection(
                backend=backend,
                fail_silently=False,
                timeout=timeout,
            )
            connection.open()
            transport_security = "STARTTLS" if getattr(settings, "EMAIL_USE_TLS", False) else (
                "SSL/TLS" if getattr(settings, "EMAIL_USE_SSL", False) else "no TLS"
            )
            self.stdout.write(
                self.style.SUCCESS(f"SUCCESS: Connected and authenticated to {host}:{port} ({transport_security}).")
            )
            connection.close()
        except socket.timeout:
            self.stdout.write(
                self.style.ERROR(f"ERROR: Connection to {host}:{port} timed out after {timeout} seconds.")
            )
            return
        except smtplib.SMTPAuthenticationError as e:
            self.stdout.write(
                self.style.ERROR(
                    f"ERROR: SMTP Authentication failed (code {e.smtp_code}).\n"
                    "The mail server rejected the configured sender credentials.\n"
                    "Please verify that EMAIL_HOST_PASSWORD in backend/.env is set to the correct IONOS account password."
                )
            )
            return
        except smtplib.SMTPConnectError as e:
            self.stdout.write(
                self.style.ERROR(f"ERROR: Failed to establish SMTP connection to {host}:{port}: {e}")
            )
            return
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"ERROR: SMTP handshake error: {type(e).__name__}: {e}")
            )
            return

        # 3. Controlled test email dispatch
        recipient = options.get("recipient")
        test_type = options.get("type", "diagnostic")

        if recipient:
            self.stdout.write(f"Dispatching test {test_type} email to {recipient} via shared email service...")
            try:
                if test_type == "reset":
                    fake_user = MagicMock()
                    fake_user.first_name = "Project Owner"
                    fake_user.username = "owner"
                    fake_user.email = recipient
                    frontend_base = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
                    sample_link = f"{frontend_base}/reset-password?token=sample_diagnostic_token_12345"
                    send_password_reset_email(fake_user, sample_link)
                elif test_type == "mfa":
                    fake_user = MagicMock()
                    fake_user.first_name = "Project Owner"
                    fake_user.username = "owner"
                    fake_user.email = recipient
                    frontend_base = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
                    sample_link = f"{frontend_base}/mfa-recovery?token=sample_diagnostic_token_12345"
                    send_mfa_recovery_email(fake_user, sample_link)
                else:
                    timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S %Z")
                    subject = "OneSmarter-CertiVerify — SMTP Delivery Test"
                    message = (
                        f"Hello,\n\n"
                        f"This is an automated SMTP delivery test message sent from OneSmarter-CertiVerify.\n"
                        f"Timestamp: {timestamp}\n"
                        f"SMTP Host: {host}:{port}\n\n"
                        f"If you received this message, your SMTP configuration is successfully accepting and transmitting emails.\n\n"
                        f"Regards,\n"
                        f"OneSmarter Support"
                    )
                    send_account_email(recipient, subject, message)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"SUCCESS: Test email accepted by SMTP server for delivery to {recipient}.\n"
                        "Note: Check your inbox (and spam folder) to verify delivery."
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"ERROR: Failed to deliver email to {recipient}: {type(e).__name__}: {e}")
                )
        else:
            self.stdout.write(
                self.style.NOTICE(
                    "TIP: To send an actual test email, specify --recipient and optional --type:\n"
                    "  python manage.py test_smtp --recipient owner@example.com --type=diagnostic\n"
                    "  python manage.py test_smtp --recipient owner@example.com --type=reset\n"
                    "  python manage.py test_smtp --recipient owner@example.com --type=mfa"
                )
            )
