# Hand-crafted additive migration — does NOT touch the existing
# Certificate table or any existing rows.
# Safe to apply on a live database with existing data.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("certificates", "0002_alter_certificate_file"),
    ]

    operations = [
        migrations.CreateModel(
            name="CertificatePDF",
            fields=[
                (
                    "certificate",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="pdf_document",
                        serialize=False,
                        to="certificates.certificate",
                    ),
                ),
                (
                    "content",
                    models.BinaryField(
                        help_text="Raw PDF bytes stored in PostgreSQL."
                    ),
                ),
                (
                    "original_filename",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text=(
                            "Original upload filename (metadata only, "
                            "not used for serving)."
                        ),
                        max_length=255,
                    ),
                ),
                (
                    "mime_type",
                    models.CharField(
                        default="application/pdf",
                        max_length=100,
                    ),
                ),
                (
                    "file_size",
                    models.PositiveBigIntegerField(
                        default=0,
                        help_text="Size in bytes.",
                    ),
                ),
                (
                    "sha256",
                    models.CharField(
                        blank=True,
                        editable=False,
                        help_text=(
                            "SHA-256 of the stored PDF bytes, "
                            "computed server-side."
                        ),
                        max_length=64,
                    ),
                ),
                (
                    "uploaded_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
            ],
            options={
                "verbose_name": "Certificate PDF",
                "verbose_name_plural": "Certificate PDFs",
            },
        ),
    ]
