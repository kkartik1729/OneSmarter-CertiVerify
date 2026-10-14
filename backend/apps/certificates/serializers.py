
from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.certificates.permissions import is_certiverify_admin
from apps.certificates.helpers import build_public_credential_url
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
    if not hasattr(obj, "pdf_document") or obj.pdf_document is None:
        return None
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
    credential_url = serializers.SerializerMethodField()
    is_credential_url_public = serializers.SerializerMethodField()

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
            "credential_url",
            "is_credential_url_public",
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
            "credential_url",
            "is_credential_url_public",
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
        try:
            return obj.pdf_document is not None
        except CertificatePDF.DoesNotExist:
            return False

    def get_pdf_download_url(self, obj: Certificate) -> str | None:
        request = self.context.get("request")
        try:
            if obj.pdf_document is None:
                return None
        except CertificatePDF.DoesNotExist:
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

    def get_credential_url(self, obj: Certificate) -> str | None:
        url, _ = build_public_credential_url(obj.certificate_number)
        return url

    def get_is_credential_url_public(self, obj: Certificate) -> bool:
        _, is_public = build_public_credential_url(obj.certificate_number)
        return is_public

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

    class Meta:
        model = CertificateTemplate
        fields = [
            "id",
            "name",
            "image",
            "image_url",
            "version",
            "file_format",
            "uploaded_by",
            "uploaded_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "uploaded_by", "uploaded_by_username", "image_url", "created_at", "updated_at"]

    def get_image_url(self, obj: CertificateTemplate) -> str | None:
        if not obj.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url

    def validate_image(self, value):
        import io
        from django.core.files.base import ContentFile
        from PIL import Image

        if value.size > 15 * 1024 * 1024:
            raise serializers.ValidationError("Template file size must not exceed 15 MB.")

        content = value.read()
        value.seek(0)

        # Inspect magic bytes — never trust extension alone
        is_png = content.startswith(b"\x89PNG\r\n\x1a\n")
        is_jpeg = content.startswith(b"\xff\xd8\xff")
        is_pdf = content.startswith(b"%PDF")

        if not (is_png or is_jpeg or is_pdf):
            raise serializers.ValidationError(
                "Unsupported file format. Please upload a valid PNG, JPG/JPEG image or single-page PDF template."
            )

        if is_pdf:
            try:
                import pypdfium2 as pdfium
                pdf = pdfium.PdfDocument(io.BytesIO(content))
                if len(pdf) < 1:
                    raise serializers.ValidationError("PDF template must contain at least 1 page.")
                page = pdf[0]
                # Render at 200 dpi for sharp vector background reproduction
                scale = 200 / 72.0
                rendered_img = page.render(scale=scale).to_pil().convert("RGB")
                buf = io.BytesIO()
                rendered_img.save(buf, format="PNG")
                png_bytes = buf.getvalue()

                safe_base = (value.name or "template").rsplit(".", 1)[0].rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
                converted_file = ContentFile(png_bytes, name=f"{safe_base}.png")
                converted_file._template_format = "PDF"
                return converted_file
            except serializers.ValidationError:
                raise
            except Exception as exc:
                raise serializers.ValidationError(f"Could not process PDF template: {exc}")

        # Validate PNG or JPEG image content with Pillow
        try:
            pil_img = Image.open(io.BytesIO(content))
            pil_img.verify()
            # Reopen to check dimensions (verify() closes the file)
            pil_img = Image.open(io.BytesIO(content))
            w, h = pil_img.size
            if w < 400 or h < 400:
                raise serializers.ValidationError(
                    f"Template image resolution is too low ({w}x{h}). Minimum required is 400x400."
                )
            value._template_format = "PNG" if is_png else "JPEG"
            return value
        except serializers.ValidationError:
            raise
        except Exception as exc:
            raise serializers.ValidationError(f"Invalid or corrupted template image: {exc}")


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
