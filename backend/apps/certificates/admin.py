"""
Django Admin configuration for the certificates app.

Administrators can:
  - View, create, edit, and delete Certificate records.
  - Upload a PDF when creating or editing a certificate
    (stored in PostgreSQL via CertificatePDF.store()).
  - Download the stored PDF directly from the admin change page.
  - Search by certificate number, title, issuer, and recipient.
  - View file metadata (filename, size, upload date, SHA-256).

No passwords, TOTP secrets, or sensitive user data are exposed here.
"""

import io

from django import forms
from django.contrib import admin, messages
from django.http import HttpResponse
from django.urls import path
from django.utils.html import format_html

from .models import Certificate, CertificatePDF


# ---------------------------------------------------------------------------
# Inline form for PDF upload / replacement
# ---------------------------------------------------------------------------

class CertificatePDFInlineForm(forms.ModelForm):
    """
    Provides a single file upload widget that the admin uses to attach or
    replace a PDF.  The BinaryField itself is never rendered directly.
    """
    pdf_upload = forms.FileField(
        required=False,
        label="Upload / Replace PDF",
        help_text=(
            "Select a PDF file (max 10 MB). "
            "The existing PDF (if any) will be replaced. "
            "Leave blank to keep the current PDF."
        ),
        widget=forms.ClearableFileInput(attrs={"accept": "application/pdf"}),
    )

    class Meta:
        model = CertificatePDF
        fields = []  # BinaryField content is handled in save() below

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Actual saving is handled by CertificatePDFInline.save_formset
        return instance


class CertificatePDFInline(admin.StackedInline):
    model = CertificatePDF
    form = CertificatePDFInlineForm
    extra = 0
    max_num = 1
    can_delete = True
    verbose_name = "Stored PDF (PostgreSQL)"
    verbose_name_plural = "Stored PDF (PostgreSQL)"
    readonly_fields = ("_pdf_meta", "sha256", "uploaded_at", "created_at")
    fields = ("pdf_upload", "_pdf_meta", "sha256", "uploaded_at", "created_at")

    def _pdf_meta(self, obj: CertificatePDF) -> str:
        if not obj or not obj.pk:
            return "No PDF stored yet."
        size_kb = obj.file_size / 1024
        return (
            f"File: {obj.original_filename or '(unnamed)'}  |  "
            f"Size: {size_kb:,.1f} KB  |  "
            f"Type: {obj.mime_type}"
        )
    _pdf_meta.short_description = "Current PDF info"


# ---------------------------------------------------------------------------
# Certificate Admin
# ---------------------------------------------------------------------------

@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "certificate_number",
        "title",
        "owner",
        "recipient_name",
        "issuer",
        "issue_date",
        "status",
        "_has_pdf",
        "created_at",
    )

    search_fields = (
        "certificate_number",
        "title",
        "issuer",
        "recipient_name",
        "owner__username",
        "owner__email",
    )

    list_filter = ("status", "issuer", "issue_date", "created_at")
    ordering = ("-created_at",)

    readonly_fields = (
        "verification_code",
        "file_sha256",
        "created_at",
        "updated_at",
        "_pdf_download_link",
    )

    fieldsets = (
        (
            "Certificate Details",
            {
                "fields": (
                    "owner",
                    "title",
                    "issuer",
                    "certificate_number",
                    "recipient_name",
                    "issue_date",
                )
            },
        ),
        (
            "Status & Verification",
            {
                "fields": (
                    "status",
                    "rejection_reason",
                    "verification_code",
                )
            },
        ),
        (
            "Legacy File (filesystem)",
            {
                "classes": ("collapse",),
                "description": (
                    "This field stores a file path on the server filesystem. "
                    "The PostgreSQL-stored PDF is managed via the inline below."
                ),
                "fields": ("file", "file_sha256"),
            },
        ),
        (
            "PostgreSQL PDF Download",
            {
                "fields": ("_pdf_download_link",),
            },
        ),
        (
            "Timestamps",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    inlines = [CertificatePDFInline]

    # ------------------------------------------------------------------
    # Custom list column: has PDF stored in PostgreSQL?
    # ------------------------------------------------------------------
    def _has_pdf(self, obj: Certificate) -> str:
        try:
            if obj.pdf_document is not None:
                return format_html(
                    '<span style="color:green;font-weight:bold;">✔ PDF stored</span>'
                )
        except CertificatePDF.DoesNotExist:
            pass
        return format_html('<span style="color:#aaa;">—</span>')
    _has_pdf.short_description = "PDF in DB"

    # ------------------------------------------------------------------
    # Download link shown in the change form
    # ------------------------------------------------------------------
    def _pdf_download_link(self, obj: Certificate) -> str:
        if not obj or not obj.pk:
            return "Save the certificate first, then upload a PDF."
        try:
            pdf = obj.pdf_document
            if pdf is None:
                return "No PDF stored in PostgreSQL for this certificate."
        except CertificatePDF.DoesNotExist:
            return "No PDF stored in PostgreSQL for this certificate."
        return format_html(
            '<a href="{}" target="_blank" '
            'style="font-weight:bold;color:#0d6efd;">'
            "⬇ Download stored PDF ({} KB)"
            "</a>",
            f"/admin/certificates/certificate/{obj.pk}/download-pdf/",
            f"{pdf.file_size / 1024:,.1f}",
        )
    _pdf_download_link.short_description = "Stored PDF"

    # ------------------------------------------------------------------
    # Inline PDF save hook  (called after the Certificate is saved)
    # ------------------------------------------------------------------
    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        for obj in formset.deleted_objects:
            obj.delete()

        # Process the inline form even if no instance was created yet
        for inline_form in formset.forms:
            upload = inline_form.files.get(
                inline_form.add_prefix("pdf_upload")
            ) or request.FILES.get("pdf_document-0-pdf_upload")

            if not upload:
                # No new file — keep whatever is already there
                continue

            raw_bytes = upload.read()
            certificate = form.instance

            try:
                CertificatePDF.store(
                    certificate=certificate,
                    raw_bytes=raw_bytes,
                    filename=upload.name,
                )
                messages.success(
                    request,
                    f"PDF '{upload.name}' stored in PostgreSQL "
                    f"({len(raw_bytes):,} bytes).",
                )
            except ValueError as exc:
                messages.error(request, f"PDF upload failed: {exc}")
            except Exception as exc:
                messages.error(
                    request,
                    f"Unexpected error storing PDF: {exc}",
                )

        for obj in instances:
            obj.save()

        formset.save_m2m()

    # ------------------------------------------------------------------
    # Extra admin URL: /admin/certificates/certificate/<pk>/download-pdf/
    # ------------------------------------------------------------------
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:pk>/download-pdf/",
                self.admin_site.admin_view(self._download_pdf_view),
                name="certificates_certificate_download_pdf",
            ),
        ]
        return custom + urls

    def _download_pdf_view(self, request, pk):
        """Stream the PostgreSQL-stored PDF to the admin user's browser."""
        cert = Certificate.objects.filter(pk=pk).first()
        if cert is None:
            return HttpResponse("Certificate not found.", status=404)

        try:
            pdf_doc = cert.pdf_document
        except CertificatePDF.DoesNotExist:
            return HttpResponse(
                "No PDF is stored in PostgreSQL for this certificate.",
                status=404,
            )

        safe_num = "".join(
            c for c in cert.certificate_number if c.isalnum() or c in "-_"
        )
        filename = f"certificate_{safe_num}.pdf"

        response = HttpResponse(
            bytes(pdf_doc.content),
            content_type="application/pdf",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Content-Length"] = pdf_doc.file_size
        response["X-Content-Type-Options"] = "nosniff"
        return response


# ---------------------------------------------------------------------------
# CertificatePDF standalone admin (read-only view for auditing)
# ---------------------------------------------------------------------------

@admin.register(CertificatePDF)
class CertificatePDFAdmin(admin.ModelAdmin):
    """
    Read-only admin view for the CertificatePDF table.
    Manage PDFs from the Certificate admin change page instead.
    """
    list_display = (
        "certificate",
        "original_filename",
        "_size_kb",
        "sha256",
        "uploaded_at",
    )
    search_fields = (
        "certificate__certificate_number",
        "original_filename",
        "sha256",
    )
    ordering = ("-uploaded_at",)
    readonly_fields = (
        "certificate",
        "original_filename",
        "mime_type",
        "file_size",
        "sha256",
        "uploaded_at",
        "created_at",
        "_pdf_download_link",
    )
    # Never show the raw binary content in the admin
    exclude = ("content",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def _size_kb(self, obj: CertificatePDF) -> str:
        return f"{obj.file_size / 1024:,.1f} KB"
    _size_kb.short_description = "Size"

    def _pdf_download_link(self, obj: CertificatePDF) -> str:
        if not obj or not obj.pk:
            return "-"
        return format_html(
            '<a href="{}" target="_blank">⬇ Download</a>',
            f"/admin/certificates/certificate/{obj.certificate_id}/download-pdf/",
        )
    _pdf_download_link.short_description = "Download"

    fields = (
        "certificate",
        "original_filename",
        "mime_type",
        "file_size",
        "sha256",
        "uploaded_at",
        "created_at",
        "_pdf_download_link",
    )