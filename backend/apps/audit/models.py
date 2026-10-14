
from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CERTIFICATE_CREATED = "CERTIFICATE_CREATED", "Certificate Created"
        CERTIFICATE_VERIFIED = "CERTIFICATE_VERIFIED", "Certificate Verified"
        CERTIFICATE_APPROVED = "CERTIFICATE_APPROVED", "Certificate Approved"
        CERTIFICATE_REJECTED = "CERTIFICATE_REJECTED", "Certificate Rejected"
        TEMPLATE_UPLOADED = "TEMPLATE_UPLOADED", "Template Uploaded"
        CSV_VALIDATED = "CSV_VALIDATED", "CSV Validated"
        BATCH_GENERATED = "BATCH_GENERATED", "Batch Generated"
        CERTIFICATE_GENERATED = "CERTIFICATE_GENERATED", "Certificate Generated"
        EMAIL_RETRY = "EMAIL_RETRY", "Email Retry"
        USER_REGISTERED = "USER_REGISTERED", "User Registered"
        USER_LOGIN = "USER_LOGIN", "User Login"
        MFA_ENABLED = "MFA_ENABLED", "MFA Enabled"
        OTHER = "OTHER", "Other"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(
        max_length=40,
        choices=Action.choices,
        db_index=True,
    )
    target_type = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["action", "-created_at"],
                name="audit_action_date_idx",
            ),
        ]

    def __str__(self):
        return f"{self.action} - {self.created_at}"
