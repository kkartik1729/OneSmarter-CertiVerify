
from django.conf import settings
from django.db import models


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        CERTIFICATE_CREATED = "CERTIFICATE_CREATED", "Certificate Created"
        CERTIFICATE_APPROVED = "CERTIFICATE_APPROVED", "Certificate Approved"
        CERTIFICATE_REJECTED = "CERTIFICATE_REJECTED", "Certificate Rejected"
        GENERAL = "GENERAL", "General"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        default=NotificationType.GENERAL,
        db_index=True,
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    certificate = models.ForeignKey(
        "certificates.Certificate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["recipient", "is_read", "-created_at"],
                name="notif_user_read_date_idx",
            ),
        ]

    def __str__(self):
        return f"{self.title} - {self.recipient}"
