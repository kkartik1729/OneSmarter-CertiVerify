
from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    class Role(models.TextChoices):
        USER = "USER", "User"
        ADMIN = "ADMIN", "Admin"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.USER,
    )

    phone = models.CharField(max_length=20, blank=True)
    organization = models.CharField(max_length=150, blank=True)

    # Google Authenticator TOTP enrollment
    mfa_enabled = models.BooleanField(default=False)
    totp_secret = models.CharField(max_length=255, blank=True, default="")
    pending_totp_secret = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    mfa_enabled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def effective_role(self):
        if getattr(self.user, "is_superuser", False) or getattr(self.user, "is_staff", False):
            return self.Role.ADMIN
        return self.role

    def __str__(self):
        return f"{self.user.username} - {self.effective_role}"


class MFARecoveryToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mfa_recovery_tokens",
    )
    token_hash = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    purpose = models.CharField(max_length=50, default="mfa_recovery")

    class Meta:
        ordering = ["-created_at"]

    def is_valid(self):
        from django.utils import timezone
        return not self.is_used and timezone.now() <= self.expires_at

    def __str__(self):
        return f"MFARecoveryToken for {self.user.username} (used={self.is_used})"


class PasswordResetRequest(models.Model):
    """
    Dedicated model for password recovery via 6-digit email OTP and
    subsequent short-lived reset authorization token.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_requests",
    )
    otp_hash = models.CharField(max_length=64, db_index=True)
    reset_token_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    otp_expires_at = models.DateTimeField()
    reset_token_expires_at = models.DateTimeField(null=True, blank=True)
    otp_verified = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=5)

    class Meta:
        ordering = ["-created_at"]

    def is_otp_valid(self):
        from django.utils import timezone
        return (
            not self.is_completed
            and not self.otp_verified
            and self.attempts < self.max_attempts
            and timezone.now() <= self.otp_expires_at
        )

    def is_reset_token_valid(self):
        from django.utils import timezone
        return (
            not self.is_completed
            and self.otp_verified
            and bool(self.reset_token_hash)
            and self.reset_token_expires_at is not None
            and timezone.now() <= self.reset_token_expires_at
        )

    def __str__(self):
        return (
            f"PasswordResetRequest for {self.user.username} "
            f"(verified={self.otp_verified}, completed={self.is_completed})"
        )


class PasswordResetToken(models.Model):
    """
    Dedicated model for email-link password reset tokens.
    Cryptographically secure, single-use, purpose-bound, and time-limited.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_tokens",
    )
    token_hash = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    purpose = models.CharField(max_length=50, default="password_reset")

    class Meta:
        ordering = ["-created_at"]

    def is_valid(self):
        from django.utils import timezone
        return not self.is_used and timezone.now() <= self.expires_at

    def __str__(self):
        return f"PasswordResetToken for {self.user.username} (used={self.is_used})"


