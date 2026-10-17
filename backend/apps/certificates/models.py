
import hashlib
import uuid

from django.conf import settings
from django.db import models


def certificate_upload_path(instance, filename):
    owner_part = instance.owner_id or "unclaimed"
    return (
        f"certificates/{owner_part}/"
        f"{uuid.uuid4().hex}_{filename}"
    )


class Certificate(models.Model):
    """
    Primary certificate record.

    The `file` FileField is kept for backward compatibility and stores a
    filesystem path only (not the binary content).  The actual PDF binary
    is stored separately in CertificatePDF.  Both can coexist.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        VERIFIED = "VERIFIED", "Verified"
        REJECTED = "REJECTED", "Rejected"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificates",
    )
    recipient_email = models.EmailField(
        max_length=254,
        blank=True,
        default="",
        db_index=True,
        help_text="Normalized recipient email address.",
    )
    title = models.CharField(max_length=200)
    issuer = models.CharField(max_length=200)
    certificate_number = models.CharField(
        max_length=100,
        unique=True,
    )
    recipient_name = models.CharField(max_length=200)
    issue_date = models.DateField()

    # A PDF is optional; verification works without a file.
    file = models.FileField(
        upload_to=certificate_upload_path,
        blank=True,
        null=True,
    )
    file_sha256 = models.CharField(
        max_length=64,
        blank=True,
        editable=False,
    )
    verification_code = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    rejection_reason = models.TextField(blank=True)

    # --- Generation & course tracking (added for certificate generation module) ---
    course = models.ForeignKey(
        "Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificates",
    )
    course_name = models.CharField(max_length=300, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    generation_batch = models.ForeignKey(
        "GenerationBatch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificates",
    )
    template = models.ForeignKey(
        "CertificateTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificates",
    )
    completion_description = models.TextField(blank=True)
    email_sent = models.BooleanField(default=False)
    email_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.recipient_name and len(self.recipient_name.strip()) >= 30:
            raise ValidationError({"recipient_name": "Student name must be 1–29 characters."})
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be earlier than start date."})

    def save(self, *args, **kwargs):
        self.certificate_number = self.certificate_number.strip().upper()
        if self.recipient_name:
            self.recipient_name = self.recipient_name.strip()
        if self.recipient_email:
            self.recipient_email = self.recipient_email.strip().lower()
        elif self.owner and getattr(self.owner, "email", None):
            self.recipient_email = self.owner.email.strip().lower()
        super().save(*args, **kwargs)

    @property
    def is_claimed(self):
        """True when the certificate is associated with a registered user account."""
        return self.owner_id is not None

    @property
    def has_pdf(self):
        """True when a PDF is stored in PostgreSQL for this certificate."""
        return hasattr(self, "pdf_document") and self.pdf_document is not None

    def __str__(self):
        return f"{self.certificate_number} - {self.title}"


# Allowed MIME types for certificate documents
_ALLOWED_MIME = {"application/pdf"}
# Max PDF upload size: 10 MB
MAX_PDF_BYTES = int(getattr(settings, "MAX_CERT_PDF_BYTES", 10 * 1024 * 1024))


class CertificatePDF(models.Model):
    """
    Stores the actual PDF binary content in PostgreSQL.

    Design:
    - One-to-one with Certificate so each certificate has at most one
      DB-stored PDF.  Replacing an existing PDF simply overwrites the row.
    - The BinaryField holds the raw bytes; the database column type is
      bytea in PostgreSQL, so the PDF never leaves the RDBMS.
    - original_filename, mime_type, and file_size are metadata only and are
      never trusted for security decisions.
    - sha256 is computed server-side from the uploaded bytes and stored for
      integrity verification.
    """

    certificate = models.OneToOneField(
        Certificate,
        on_delete=models.CASCADE,
        related_name="pdf_document",
        primary_key=True,
    )
    content = models.BinaryField(
        help_text="Raw PDF bytes stored in PostgreSQL.",
    )
    original_filename = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Original upload filename (metadata only, not used for serving).",
    )
    mime_type = models.CharField(
        max_length=100,
        default="application/pdf",
    )
    file_size = models.PositiveBigIntegerField(
        default=0,
        help_text="Size in bytes.",
    )
    sha256 = models.CharField(
        max_length=64,
        blank=True,
        editable=False,
        help_text="SHA-256 of the stored PDF bytes, computed server-side.",
    )
    uploaded_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Certificate PDF"
        verbose_name_plural = "Certificate PDFs"

    # ------------------------------------------------------------------
    # Class-level helper — used by views and admin
    # ------------------------------------------------------------------

    @classmethod
    def store(cls, certificate: Certificate, raw_bytes: bytes, filename: str = "") -> "CertificatePDF":
        """
        Insert or replace the PDF for *certificate*.

        Validates that the content starts with the PDF magic bytes (%PDF)
        and is within the configured size limit.  Raises ValueError on
        invalid input.  Returns the saved CertificatePDF instance.
        """
        if not raw_bytes:
            raise ValueError("Uploaded file is empty.")

        if len(raw_bytes) > MAX_PDF_BYTES:
            raise ValueError(
                f"File size {len(raw_bytes):,} bytes exceeds the "
                f"{MAX_PDF_BYTES // (1024 * 1024)} MB limit."
            )

        # Validate PDF magic bytes (%PDF)
        if not raw_bytes[:4] == b"%PDF":
            raise ValueError(
                "The uploaded file does not appear to be a valid PDF "
                "(missing %PDF header)."
            )

        sha256 = hashlib.sha256(raw_bytes).hexdigest()

        # Safe filename: strip path components
        safe_name = (filename or "certificate.pdf").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        if not safe_name.lower().endswith(".pdf"):
            safe_name = "certificate.pdf"

        obj, _ = cls.objects.update_or_create(
            certificate=certificate,
            defaults={
                "content": raw_bytes,
                "original_filename": safe_name[:255],
                "mime_type": "application/pdf",
                "file_size": len(raw_bytes),
                "sha256": sha256,
            },
        )
        return obj

    def __str__(self):
        return f"PDF for {self.certificate.certificate_number} ({self.file_size:,} bytes)"


# ---------------------------------------------------------------------------
# Course model
# ---------------------------------------------------------------------------

class Course(models.Model):
    """A course / program that certificates are issued for."""

    name = models.CharField(max_length=300)
    title = models.CharField(
        max_length=300,
        help_text="Certificate title (e.g. 'Certificate of Completion').",
    )
    issuer = models.CharField(
        max_length=300,
        help_text="Issuing organization name.",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_courses",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be earlier than start date."})

    def __str__(self):
        return f"{self.name} ({self.issuer})"


# ---------------------------------------------------------------------------
# Certificate template model
# ---------------------------------------------------------------------------

def template_upload_path(instance, filename):
    return f"certificate_templates/{uuid.uuid4().hex}_{filename}"


class CertificateTemplate(models.Model):
    """An uploaded certificate background and its editable source when available."""

    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to=template_upload_path)
    # Preserve uploaded PDF bytes. ``image`` remains the legacy first-page preview
    # so existing clients and records continue to work without a schema rewrite.
    original_pdf = models.FileField(upload_to=template_upload_path, blank=True, null=True)
    version = models.PositiveIntegerField(default=1)
    file_format = models.CharField(max_length=10, default="PNG")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_templates",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Optional completion description text. If empty, the template is assumed to contain pre-printed text.",
    )
    layout_config = models.JSONField(
        blank=True,
        default=dict,
        help_text="Optional per-template coordinates and rendering configuration.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Batch generation tracking
# ---------------------------------------------------------------------------

class GenerationBatch(models.Model):
    """Tracks a bulk certificate generation job."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generation_batches",
    )
    template = models.ForeignKey(
        CertificateTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generation_batches",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    total_rows = models.PositiveIntegerField(default=0)
    successful = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    skipped_duplicates = models.PositiveIntegerField(default=0)
    emails_sent = models.PositiveIntegerField(default=0)
    emails_failed = models.PositiveIntegerField(default=0)
    error_report = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generation_batches",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Generation batches"

    def __str__(self):
        course_name = self.course.name if self.course else "No course"
        return f"Batch #{self.pk} — {course_name} ({self.status})"
