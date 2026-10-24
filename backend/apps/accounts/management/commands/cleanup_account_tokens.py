from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import (
    EmailVerificationToken,
    MFARecoveryToken,
    PasswordResetRequest,
    PasswordResetToken,
)


class Command(BaseCommand):
    help = "Delete expired or consumed account verification and recovery tokens."

    def handle(self, *args, **options):
        now = timezone.now()
        with transaction.atomic():
            removed = {
                "email_verification_tokens": EmailVerificationToken.objects.filter(
                    Q(is_used=True) | Q(expires_at__lt=now)
                ).delete()[0],
                "mfa_recovery_tokens": MFARecoveryToken.objects.filter(
                    Q(is_used=True) | Q(expires_at__lt=now)
                ).delete()[0],
                "password_reset_tokens": PasswordResetToken.objects.filter(
                    Q(is_used=True) | Q(expires_at__lt=now)
                ).delete()[0],
                "password_reset_requests": PasswordResetRequest.objects.filter(
                    Q(is_completed=True)
                    | Q(otp_expires_at__lt=now)
                    | Q(reset_token_expires_at__lt=now)
                ).delete()[0],
            }
        total = sum(removed.values())
        self.stdout.write(self.style.SUCCESS(f"Removed {total} expired or consumed account token records."))
