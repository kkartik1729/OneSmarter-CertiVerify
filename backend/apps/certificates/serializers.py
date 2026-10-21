
from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.certificates.permissions import is_certiverify_admin
from .models import Certificate, CertificatePDF, Course, CertificateTemplate, GenerationBatch

User = get_user_model()


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _pdf_download_url(obj: Certificate, request) -> str | None:
    """
    Return the absolute URL for downloading the DB-stored PDF,
    or None when no PDF is stored.
    """
    if request is None:
        return f"/api/certificates/{obj.pk}/pdf/download/"
    return request.build_absolute_uri(f"/api/certificates/{obj.pk}/pdf/download/")


# ---------------------------------------------------------------------------
# Main certificate serializer
# ---------------------------------------------------------------------------

class CertificateSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
    )
    owner_username = serializers.CharField(
        source="owner.username",
        read_only=True,
        default=None,
    )
    recipient_email = serializers.EmailField(
        required=False,
        allow_blank=True,
    )
    is_claimed = serializers.BooleanField(read_only=True)
    # Read-only fields for PDF metadata — null when no PDF is stored
    has_pdf = serializers.SerializerMethodField()
    pdf_download_url = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = [
            "id",
            "owner",
            "owner_username",
            "recipient_email",
            "is_claimed",
            "title",
            "issuer",
            "certificate_number",
            "recipient_name",
            "issue_date",
            "course",
            "course_name",
            "template",
            "completion_description",
            "start_date",
            "end_date",
            "generation_batch",
            "email_sent",
            "email_error",
            "file",           # legacy/generated file path
            "file_sha256",    # SHA-256 of generated/uploaded file
            "has_pdf",        # True when PDF is stored in PostgreSQL
            "pdf_download_url",  # download URL when has_pdf is True
            "image_url",
            "download_url",
            "verification_code",
            "status",
            "rejection_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "owner_username",
            "is_claimed",
            "file_sha256",
            "has_pdf",
            "pdf_download_url",
            "image_url",
            "download_url",
            "verification_code",
            "status",
            "rejection_reason",
            "created_at",
            "updated_at",
        ]

    def to_internal_value(self, data):
        # Allow either owner_id or owner in the incoming data
        if hasattr(data, "copy"):
            data = data.copy()
        else:
            data = dict(data)
        if "owner_id" in data and "owner" not in data:
            data["owner"] = data["owner_id"]
        return super().to_internal_value(data)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret["owner_id"] = instance.owner_id
        return ret

    def get_has_pdf(self, obj: Certificate) -> bool:
        # List/detail querysets annotate existence so serialization does not
        # fetch the related PDF row and its potentially large binary content.
        if hasattr(obj, "_has_pdf"):
            return bool(obj._has_pdf)
        return CertificatePDF.objects.filter(certificate_id=obj.pk).exists()

    def get_pdf_download_url(self, obj: Certificate) -> str | None:
        request = self.context.get("request")
        if not self.get_has_pdf(obj):
            return None
        return _pdf_download_url(obj, request)

    def get_image_url(self, obj: Certificate) -> str | None:
        if not obj.file:
            return None
        request = self.context.get("request")
        path = f"/api/certificates/{obj.pk}/image/"
        return request.build_absolute_uri(path) if request else path

    def get_download_url(self, obj: Certificate) -> str | None:
        request = self.context.get("request")
        if self.get_has_pdf(obj):
            return self.get_pdf_download_url(obj)
        if obj.file:
            path = f"/api/certificates/{obj.pk}/image/?download=true"
            return request.build_absolute_uri(path) if request else path
        return None

    def validate_recipient_name(self, value):
        trimmed = (value or "").strip()
        if not trimmed:
            raise serializers.ValidationError("Student name is required.")
        if len(trimmed) >= 30:
            raise serializers.ValidationError(
                f"Student name must be 1–29 characters (currently {len(trimmed)} characters: '{trimmed}')."
            )
        return trimmed

    def validate_certificate_number(self, value):
        value = value.strip().upper()

        queryset = Certificate.objects.filter(
            certificate_number__iexact=value
        )
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                "This certificate number already exists."
            )

        return value

    def validate_file(self, value):
        """Validate the legacy FileField upload (filesystem-backed)."""
        allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg"}
        filename = value.name.lower()

        if not any(filename.endswith(ext) for ext in allowed_extensions):
            raise serializers.ValidationError(
                "Only PDF, PNG, JPG, and JPEG files are allowed."
            )

        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError(
                "File size must not exceed 10 MB."
            )

        return value

    def validate(self, attrs):
        # 1. Date validation: end_date >= start_date
        start_date = attrs.get("start_date") or (self.instance.start_date if self.instance else None)
        end_date = attrs.get("end_date") or (self.instance.end_date if self.instance else None)
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                "end_date": "End date cannot be earlier than start date."
            })

        request = self.context.get("request")
        user = getattr(request, "user", None)

        if user and user.is_authenticated:
            if is_certiverify_admin(user):
                owner = attrs.get("owner")
                recipient_email = (attrs.get("recipient_email") or "").strip().lower()

                # When admin creates a certificate
                if self.instance is None:
                    if not owner and not recipient_email:
                        raise serializers.ValidationError({
                            "owner_id": "Please select a registered user account or enter a recipient email address.",
                            "recipient_email": "Please select a registered user account or enter a recipient email address.",
                        })
                    if owner and not owner.is_active:
                        raise serializers.ValidationError({
                            "owner_id": "Selected user account is inactive."
                        })
                else:
                    # When admin updates a certificate
                    if owner and not owner.is_active:
                        raise serializers.ValidationError({
                            "owner_id": "Selected user account is inactive."
                        })
            else:
                # Normal user: cannot assign to another account
                client_owner = attrs.get("owner")
                if client_owner and client_owner != user:
                    raise serializers.ValidationError({
                        "owner": "You cannot assign certificates to other user accounts."
                    })
                attrs["owner"] = user
                if not attrs.get("recipient_email") and user.email:
                    attrs["recipient_email"] = user.email.lower()
        return attrs


# ---------------------------------------------------------------------------
# Review serializer (unchanged)
# ---------------------------------------------------------------------------

class CertificateReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certificate
        fields = ["status", "rejection_reason"]

    def validate(self, attrs):
        new_status = attrs.get("status")

        if new_status not in (
            Certificate.Status.VERIFIED,
            Certificate.Status.REJECTED,
        ):
            raise serializers.ValidationError({
                "status": "Choose VERIFIED or REJECTED."
            })

        if (
            new_status == Certificate.Status.REJECTED
            and not attrs.get("rejection_reason", "").strip()
        ):
            raise serializers.ValidationError({
                "rejection_reason": "A reason is required for rejection."
            })

        return attrs


# ---------------------------------------------------------------------------
# Public verification serializer (unchanged)
# ---------------------------------------------------------------------------

class PublicCertificateVerificationSerializer(serializers.ModelSerializer):
    found = serializers.SerializerMethodField()
    verification_result = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = [
            "certificate_number",
            "found",
            "verification_result",
            "message",
            "title",
            "issuer",
            "issue_date",
        ]

    def get_found(self, obj):
        return True

    def get_verification_result(self, obj):
        return "FOUND"

    def get_message(self, obj):
        return "Certificate found in the database."


# ---------------------------------------------------------------------------
# Course serializer
# ---------------------------------------------------------------------------

class CourseSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(
        source="created_by.username",
        read_only=True,
    )

    class Meta:
        model = Course
        fields = [
            "id",
            "name",
            "title",
            "issuer",
            "start_date",
            "end_date",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_by_username", "created_at", "updated_at"]

    def validate(self, attrs):
        start_date = attrs.get("start_date") or (self.instance.start_date if self.instance else None)
        end_date = attrs.get("end_date") or (self.instance.end_date if self.instance else None)

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                "end_date": "End date cannot be earlier than start date."
            })
        return attrs


# ---------------------------------------------------------------------------
# Certificate Template serializer
# ---------------------------------------------------------------------------

class CertificateTemplateSerializer(serializers.ModelSerializer):
    uploaded_by_username = serializers.CharField(
        source="uploaded_by.username",
        read_only=True,
    )
    image_url = serializers.SerializerMethodField()
    # Use FileField rather than DRF's ImageField so that DRF's internal image.verify()
    # does not fail on Figma PNGs with complex metadata chunks (iCCP, pHYs, etc.)
    image = serializers.FileField(required=True)
    original_pdf = serializers.FileField(required=False, allow_null=True, write_only=True)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        default="",
    )

    class Meta:
        model = CertificateTemplate
        fields = [
            "id",
            "name",
            "image",
            "original_pdf",
            "image_url",
            "description",
            "layout_config",
            "version",
            "file_format",
            "uploaded_by",
            "uploaded_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "uploaded_by", "uploaded_by_username", "image_url", "created_at", "updated_at"]

    def create(self, validated_data):
        original_pdf = validated_data.pop("original_pdf", None)
        image = validated_data.get("image")
        if original_pdf is None:
            original_pdf = getattr(image, "_original_pdf", None)
        obj = super().create(validated_data)
        if original_pdf:
            obj.original_pdf.save(original_pdf.name, original_pdf, save=True)
        return obj

    def update(self, instance, validated_data):
        original_pdf = validated_data.pop("original_pdf", None)
        image = validated_data.get("image")
        if original_pdf is None:
            original_pdf = getattr(image, "_original_pdf", None)
        obj = super().update(instance, validated_data)
        if original_pdf:
            obj.original_pdf.save(original_pdf.name, original_pdf, save=True)
        return obj

    def get_image_url(self, obj: CertificateTemplate) -> str | None:
        if not obj.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url

    def validate_image(self, value):
        import io
        import logging
        from django.core.files.base import ContentFile
        from .generator import (
            MAX_TEMPLATE_PIXELS,
            TemplateImageError,
            _safe_open_raster,
            pdf_template_render_scale,
        )

        logger = logging.getLogger(__name__)

        # Support templates up to 25 MB
        if value.size > 25 * 1024 * 1024:
            raise serializers.ValidationError("Template file size must not exceed 25 MB.")

        content = value.read()
        value.seek(0)

        if not content:
            raise serializers.ValidationError("Uploaded template file is empty.")

        # Inspect magic bytes — never trust extension alone
        is_png = content.startswith(b"\x89PNG\r\n\x1a\n")
        is_jpeg = content.startswith(b"\xff\xd8\xff")
        is_pdf = content.startswith(b"%PDF")

        if not (is_png or is_jpeg or is_pdf):
            raise serializers.ValidationError(
                "Unsupported file format. Please upload a valid PNG, JPG/JPEG image or single-page PDF template."
            )

        safe_base = (value.name or "template").rsplit(".", 1)[0].rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        safe_base = "".join(c for c in safe_base if c.isalnum() or c in ("-", "_"))[:60] or "template"

        if is_pdf:
            try:
                import pypdfium2 as pdfium
                pdf = pdfium.PdfDocument(io.BytesIO(content))
                try:
                    if len(pdf) < 1:
                        raise serializers.ValidationError("PDF template must contain at least 1 page.")
                    page = pdf[0]
                    width, height = page.get_size()
                    scale = pdf_template_render_scale(width, height)
                    bitmap = page.render(scale=scale)
                    try:
                        rendered_img = bitmap.to_pil().convert("RGB")
                    finally:
                        bitmap.close()
                    try:
                        buf = io.BytesIO()
                        rendered_img.save(buf, format="PNG", dpi=(scale * 72.0, scale * 72.0))
                        png_bytes = buf.getvalue()
                    finally:
                        rendered_img.close()
                finally:
                    pdf.close()

                converted_file = ContentFile(png_bytes, name=f"{safe_base}.png")
                converted_file._template_format = "PDF"
                # If the client did not send a second copy, preserve the original
                # upload on the converted preview object for create/update hooks.
                converted_file._original_pdf = ContentFile(content, name=f"{safe_base}.pdf")
                return converted_file
            except serializers.ValidationError:
                raise
            except Exception as exc:
                logger.warning("Could not process PDF template: %s", exc)
                raise serializers.ValidationError(f"Could not process PDF template: {exc}")

        # Validate PNG or JPEG image content with Pillow
        # Safely decode Figma PNGs (including transparency, alpha channels, and metadata chunks)
        pil_img = None
        try:
            pil_img = _safe_open_raster(io.BytesIO(content))
            w, h = pil_img.info.get("_certify_source_dimensions", pil_img.size)
            if w < 300 or h < 300:
                pil_img.close()
                raise serializers.ValidationError(
                    f"Template image resolution is too low ({w}x{h}). Minimum required is 300x300."
                )

            if w * h > MAX_TEMPLATE_PIXELS:
                # Keep the original uploaded source unchanged; validation and
                # generation both apply the bounded working-raster policy.
                pil_img.close()
                value.seek(0)
                return value

            supported_modes = {"RGB", "RGBA", "P", "PA", "L", "LA", "CMYK", "1"}
            if pil_img.mode not in supported_modes:
                pil_img.close()
                raise serializers.ValidationError(
                    f"Unsupported color mode '{pil_img.mode}'. Supported modes are RGB, RGBA, Grayscale, and Palette."
                )

            # Re-encode PNG cleanly to strip problematic non-standard metadata chunks (e.g. invalid iCCP)
            # while strictly preserving 100% resolution, aspect ratio, and alpha transparency
            if is_png:
                out_buf = io.BytesIO()
                # If Palette mode with transparency, convert to RGBA so transparency is pristine
                if pil_img.mode in ("P", "PA"):
                    pil_clean = pil_img.convert("RGBA")
                elif pil_img.mode in ("L", "LA", "1"):
                    pil_clean = pil_img.convert("RGBA" if "A" in pil_img.mode else "RGB")
                elif pil_img.mode == "CMYK":
                    pil_clean = pil_img.convert("RGB")
                else:
                    pil_clean = pil_img

                pil_clean.save(out_buf, format="PNG", optimize=False)
                clean_bytes = out_buf.getvalue()
                saved_file = ContentFile(clean_bytes, name=f"{safe_base}.png")
                saved_file._template_format = "PNG"
                if pil_clean is not pil_img:
                    pil_clean.close()
                pil_img.close()
                return saved_file
            else:
                out_buf = io.BytesIO()
                pil_clean = pil_img.convert("RGB") if pil_img.mode != "RGB" else pil_img
                pil_clean.save(out_buf, format="JPEG", quality=95)
                clean_bytes = out_buf.getvalue()
                saved_file = ContentFile(clean_bytes, name=f"{safe_base}.jpg")
                saved_file._template_format = "JPEG"
                if pil_clean is not pil_img:
                    pil_clean.close()
                pil_img.close()
                return saved_file

        except serializers.ValidationError:
            raise
        except Exception as exc:
            if pil_img is not None:
                pil_img.close()
            logger.warning(
                "Failed to decode uploaded image (size=%d bytes, format=%s): %s",
                len(content),
                "PNG" if is_png else "JPEG",
                exc,
            )
            if isinstance(exc, TemplateImageError):
                raise serializers.ValidationError(str(exc))
            raise serializers.ValidationError(f"Invalid or unreadable template image: {exc}")


# ---------------------------------------------------------------------------
# Generation Batch serializer
# ---------------------------------------------------------------------------

class GenerationBatchSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source="course.name", read_only=True)
    template_name = serializers.CharField(source="template.name", read_only=True)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = GenerationBatch
        fields = [
            "id",
            "course",
            "course_name",
            "template",
            "template_name",
            "status",
            "total_rows",
            "successful",
            "failed",
            "skipped_duplicates",
            "emails_sent",
            "emails_failed",
            "error_report",
            "created_by",
            "created_by_username",
            "created_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "total_rows",
            "successful",
            "failed",
            "skipped_duplicates",
            "emails_sent",
            "emails_failed",
            "error_report",
            "created_by",
            "created_by_username",
            "created_at",
            "completed_at",
        ]
