
from django.conf import settings
from django.db import models


class VerificationAttempt(models.Model):
    class Result(models.TextChoices):
        FOUND = "FOUND", "Found"
        VERIFIED = "VERIFIED", "Verified"
        PENDING = "PENDING", "Pending"
        REJECTED = "REJECTED", "Rejected"
        NOT_FOUND = "NOT_FOUND", "Not Found"

    certificate = models.ForeignKey(
        "certificates.Certificate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verification_attempts",
    )
    certificate_number = models.CharField(max_length=100, db_index=True)
    result = models.CharField(
        max_length=20,
        choices=Result.choices,
        db_index=True,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verification_attempts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["certificate_number", "-created_at"],
                name="verify_number_date_idx",
            ),
        ]

    def __str__(self):
        return f"{self.certificate_number} - {self.result}"
