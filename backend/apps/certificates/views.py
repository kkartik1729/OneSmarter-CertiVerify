import base64
import csv
import hashlib
import io
import logging
import re
import uuid
from datetime import datetime

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import models, transaction
from django.db.models import Q
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.exceptions import APIException
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.audit.services import log_action
from apps.notifications.models import Notification
from apps.verification.authentication import OptionalJWTAuthentication
from apps.verification.models import VerificationAttempt

from .emails import send_certificate_issued_email
from .generator import generate_certificate_image, load_template_image
from .models import Certificate, CertificatePDF, CertificateTemplate, Course, GenerationBatch
from .permissions import (
    IsCertiVerifyAdmin,
    IsOwnerOrCertiVerifyAdmin,
    is_certiverify_admin,
)
from .serializers import (
    CertificateSerializer,
    CertificateTemplateSerializer,
    CourseSerializer,
    GenerationBatchSerializer,
)

User = get_user_model()

logger = logging.getLogger(__name__)


def _missing_template_fields(template, values, custom_values=None):
    """Return unresolved placeholders configured in the saved template layout."""
    layout = getattr(template, "layout_config", None) or {}
    custom_values = custom_values or {}
    aliases = {
        "recipient_name": "student_name",
        "student_name": "student_name",
        "certificate_id": "certificate_number",
        "certificate_number": "certificate_number",
        "course_description": "completion_description",
        "issuer_name": "issuer",
    }
    required = set()
    for element in layout.get("elements", []) or []:
        if isinstance(element, dict) and isinstance(element.get("text"), str):
            required.update(re.findall(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}", element["text"]))
    missing = []
    optional_fields = {
        "course_name", "course_description", "completion_description",
        "start_date", "end_date", "issue_date",
    }
    for field in sorted(required):
        source_field = aliases.get(field, field)
        value = values.get(source_field)
        if value is None or not str(value).strip():
            value = custom_values.get(field, custom_values.get(source_field, ""))
        if (
            value is None
            or not str(value).strip()
            or str(value).strip().lower() in {"none", "null"}
            or re.search(r"\{\{\s*[A-Za-z_][A-Za-z0-9_]*\s*\}\}", str(value))
        ):
            # These values are optional template content. An empty replacement
            # is safer than blocking generation or leaving a placeholder behind.
            if field not in optional_fields:
                missing.append(field)
    return missing


def _send_and_record_certificate_email(certificate):
    """Keep email delivery outcome separate from the already-created certificate."""
    try:
        email_sent, email_error = send_certificate_issued_email(certificate)
    except Exception:
        logger.exception("Certificate email delivery raised unexpectedly for %s", certificate.certificate_number)
        email_sent, email_error = False, "Email delivery failed. Use the existing retry action to try again."

    certificate.email_sent = bool(email_sent)
    certificate.email_error = (email_error or "")[:2000]
    try:
        certificate.save(update_fields=["email_sent", "email_error"])
    except Exception:
        logger.exception("Could not persist email status for generated certificate %s", certificate.certificate_number)
        certificate.email_error = (
            "Email was accepted, but its delivery status could not be saved."
            if email_sent
            else "Email delivery failed and its status could not be saved."
        )
    return bool(email_sent), certificate.email_error


# ---------------------------------------------------------------------------
# Certificate list / create
# ---------------------------------------------------------------------------

class CertificateListCreateView(generics.ListCreateAPIView):
    """
    Authenticated users can create certificates and view their own records.
    Administrators can view all certificate records.
    """

    serializer_class = CertificateSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = Certificate.objects.select_related("owner").prefetch_related(
            "pdf_document"
        )
        if is_certiverify_admin(self.request.user):
            return qs

        user = self.request.user
        if user and user.is_authenticated:
            profile = getattr(user, "profile", None)
            if profile and getattr(profile, "email_verified", False):
                from apps.certificates.services import claim_unclaimed_certificates_for_user
                claim_unclaimed_certificates_for_user(user)

        # Re-evaluate queryset AFTER claiming so newly-claimed certs appear immediately
        return Certificate.objects.select_related("owner").prefetch_related(
            "pdf_document"
        ).filter(owner=self.request.user)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def perform_create(self, serializer):
        uploaded_file = serializer.validated_data.get("file")
        file_hash = ""

        if uploaded_file:
            digest = hashlib.sha256()
            for chunk in uploaded_file.chunks():
                digest.update(chunk)
            file_hash = digest.hexdigest()
            uploaded_file.seek(0)

        # Determine owner & recipient_email:
        if is_certiverify_admin(self.request.user):
            owner = serializer.validated_data.get("owner", None)
            recipient_email = serializer.validated_data.get("recipient_email", "")
            if not recipient_email and owner and owner.email:
                recipient_email = owner.email.lower()
        else:
            owner = self.request.user
            recipient_email = self.request.user.email.lower()

        with transaction.atomic():
            certificate = serializer.save(
                owner=owner,
                recipient_email=recipient_email,
                file_sha256=file_hash,
            )

            # If uploaded file is a PDF, also store directly in PostgreSQL via CertificatePDF
            if uploaded_file:
                try:
                    uploaded_file.seek(0)
                    raw_bytes = uploaded_file.read()
                    uploaded_file.seek(0)
                    if raw_bytes[:4] == b"%PDF":
                        CertificatePDF.store(
                            certificate=certificate,
                            raw_bytes=raw_bytes,
                            filename=uploaded_file.name,
                        )
                except Exception as exc:
                    logger.warning("Could not auto-store PDF in CertificatePDF: %s", exc)

            log_action(
                action=AuditLog.Action.CERTIFICATE_CREATED,
                actor=self.request.user,
                target_type="Certificate",
                target_id=certificate.id,
                description=(
                    f"Certificate created and assigned to "
                    f"{owner.username if owner else (recipient_email or 'unregistered recipient')}"
                ),
                metadata={
                    "certificate_number": certificate.certificate_number,
                    "owner_id": owner.id if owner else None,
                    "owner_username": owner.username if owner else None,
                    "recipient_email": recipient_email,
                },
                ip_address=self.request.META.get("REMOTE_ADDR"),
            )


# ---------------------------------------------------------------------------
# Certificate detail
# ---------------------------------------------------------------------------

class CertificateDetailView(generics.RetrieveUpdateAPIView):
    """
    Users can view their own certificate details.
    Administrators can view or update (e.g. reassign owner) any certificate.
    """

    serializer_class = CertificateSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrCertiVerifyAdmin]
    queryset = Certificate.objects.select_related("owner").prefetch_related(
        "pdf_document"
    )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def perform_update(self, serializer):
        from rest_framework.exceptions import PermissionDenied
        if not is_certiverify_admin(self.request.user):
            raise PermissionDenied("Only administrators can update certificates or reassign ownership.")

        old_owner = serializer.instance.owner
        certificate = serializer.save()
        new_owner = certificate.owner

        if old_owner != new_owner:
            log_action(
                action=AuditLog.Action.OTHER,
                actor=self.request.user,
                target_type="Certificate",
                target_id=certificate.id,
                description=f"Certificate owner reassigned from {old_owner.username} to {new_owner.username}",
                metadata={
                    "certificate_number": certificate.certificate_number,
                    "old_owner_id": old_owner.id,
                    "old_owner_username": old_owner.username,
                    "new_owner_id": new_owner.id,
                    "new_owner_username": new_owner.username,
                },
                ip_address=self.request.META.get("REMOTE_ADDR"),
            )


# ---------------------------------------------------------------------------
# Certificate review (disabled — verification is by DB existence)
# ---------------------------------------------------------------------------

class CertificateReviewView(APIView):
    """
    Manual certificate approval/rejection is disabled.
    Verification is determined by database existence.
    Kept to avoid breaking existing URL imports.
    """

    permission_classes = [IsAuthenticated, IsCertiVerifyAdmin]

    def patch(self, request, pk):
        get_object_or_404(Certificate, pk=pk)
        return Response(
            {
                "detail": (
                    "Manual status changes are disabled. "
                    "Verification is determined by whether the "
                    "certificate exists in the database."
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


# ---------------------------------------------------------------------------
# Public certificate verification (unchanged)
# ---------------------------------------------------------------------------

class CertificateVerifyView(APIView):
    """
    Public verification endpoint.

    Only a certificate with the current VERIFIED status returns verified details.
    Other statuses return a public status summary without recipient or course data.
    """

    permission_classes = [AllowAny]
    authentication_classes = [OptionalJWTAuthentication]

    def get(self, request, certificate_number):
        normalized_number = (certificate_number or "").strip().upper()

        if not normalized_number:
            response = Response(
                {
                    "certificate_number": "",
                    "found": False,
                    "verification_result": "NOT_VERIFIED",
                    "message": "Certificate number is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            return response

        certificate = Certificate.objects.filter(
            certificate_number=normalized_number
        ).first()

        with transaction.atomic():
            VerificationAttempt.objects.create(
                certificate=certificate,
                certificate_number=normalized_number,
                result=(
                    VerificationAttempt.Result.FOUND
                    if certificate is not None
                    else VerificationAttempt.Result.NOT_FOUND
                ),
                requested_by=(
                    request.user if request.user.is_authenticated else None
                ),
            )

        if certificate is None:
            response = Response(
                {
                    "certificate_number": normalized_number,
                    "found": False,
                    "verification_result": "NOT_VERIFIED",
                    "message": "Certificate was not found in the database.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            return response

        certificate_status = certificate.status
        is_verified = certificate_status == Certificate.Status.VERIFIED
        if certificate_status == Certificate.Status.PENDING:
            verification_result = "PENDING"
            message = "This certificate is in the registry but is pending verification."
        elif certificate_status == Certificate.Status.REJECTED:
            verification_result = "REJECTED"
            message = "This certificate was reviewed and rejected."
        elif is_verified:
            verification_result = "VERIFIED"
            message = "This certificate has been verified against the OneSmarter-CertiVerify registry."
        else:
            verification_result = "NOT_VERIFIED"
            message = "This certificate is not currently verified."

        data = {
            "certificate_number": certificate.certificate_number,
            "found": True,
            "verification_result": verification_result,
            "status": certificate_status,
            "message": message,
        }
        if is_verified:
            data.update({
                "title": certificate.title,
                "issuer": certificate.issuer,
                "issue_date": certificate.issue_date,
                # Public credential fields only. Never expose email, internal IDs, or secrets.
                "recipient_name": certificate.recipient_name,
                "course_name": certificate.course_name or "",
                "start_date": certificate.start_date,
                "end_date": certificate.end_date,
                "preview_url": (
                    f"/certificates/verify/{certificate.certificate_number}/preview/"
                    if _has_public_preview_source(certificate)
                    else None
                ),
            })

        response = Response(data, status=status.HTTP_200_OK)
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response


def _has_public_preview_source(certificate):
    if certificate.file:
        try:
            if certificate.file.storage.exists(certificate.file.name):
                return True
        except Exception:
            pass
    try:
        return bool(certificate.pdf_document.content)
    except CertificatePDF.DoesNotExist:
        return False


class PublicCertificatePreviewView(APIView):
    """Serve only the saved preview for a verified certificate, keyed by its public number."""
    permission_classes = [AllowAny]
    authentication_classes = [OptionalJWTAuthentication]

    def get(self, request, certificate_number):
        certificate = get_object_or_404(
            Certificate, certificate_number=(certificate_number or "").strip().upper()
        )
        if certificate.status != Certificate.Status.VERIFIED or not _has_public_preview_source(certificate):
            return Response({"detail": "No public certificate preview is available."}, status=status.HTTP_404_NOT_FOUND)
        try:
            sources = []
            if certificate.file:
                try:
                    if certificate.file.storage.exists(certificate.file.name):
                        with certificate.file.open("rb") as source:
                            sources.append(source.read())
                except Exception:
                    logger.info("Legacy certificate file unavailable for %s", certificate.certificate_number)
            try:
                sources.append(bytes(certificate.pdf_document.content))
            except CertificatePDF.DoesNotExist:
                pass

            raw_bytes = None
            for source_bytes in sources:
                try:
                    try:
                        image = Image.open(io.BytesIO(source_bytes)).convert("RGB")
                    except Exception:
                        import pypdfium2 as pdfium
                        pdf = pdfium.PdfDocument(source_bytes)
                        if len(pdf) < 1:
                            continue
                        image = pdf[0].render(scale=1.5).to_pil().convert("RGB")
                    preview = io.BytesIO()
                    image.save(preview, format="PNG")
                    raw_bytes = preview.getvalue()
                    break
                except Exception:
                    logger.info("Certificate preview source could not be rendered for %s", certificate.certificate_number)

            if raw_bytes is None:
                return Response({"detail": "Certificate preview is unavailable."}, status=status.HTTP_404_NOT_FOUND)
            response = HttpResponse(raw_bytes, content_type="image/png")
            response["X-Content-Type-Options"] = "nosniff"
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            return response
        except Exception:
            logger.exception("Unable to serve public preview for certificate %s", certificate.certificate_number)
            return Response({"detail": "Certificate preview is unavailable."}, status=status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# PDF Upload  (POST /api/certificates/<pk>/pdf/)
# ---------------------------------------------------------------------------

class CertificatePDFUploadView(APIView):
    """
    POST /api/certificates/<pk>/pdf/

    Admin-only endpoint to upload or replace the PostgreSQL-stored PDF for a
    certificate.  The multipart body must contain a single field named `file`.

    Validates:
    - JWT authentication + admin role
    - Certificate exists
    - The uploaded field name is 'file'
    - The file starts with the PDF magic bytes (%PDF)
    - The file size does not exceed MAX_CERT_PDF_BYTES (default 10 MB)

    Returns the certificate's updated serialized representation.
    """

    permission_classes = [IsAuthenticated, IsCertiVerifyAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        certificate = get_object_or_404(Certificate, pk=pk)

        upload = request.FILES.get("file")
        if not upload:
            return Response(
                {"detail": "No file provided. Send the PDF as the 'file' field."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_bytes = upload.read()

        try:
            pdf = CertificatePDF.store(
                certificate=certificate,
                raw_bytes=raw_bytes,
                filename=upload.name,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception(
                "Unexpected error storing PDF for certificate %s", pk
            )
            return Response(
                {"detail": "Failed to store PDF. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        log_action(
            action=AuditLog.Action.OTHER,
            actor=request.user,
            target_type="Certificate",
            target_id=certificate.id,
            description="PDF uploaded and stored in PostgreSQL",
            metadata={
                "certificate_number": certificate.certificate_number,
                "filename": pdf.original_filename,
                "file_size": pdf.file_size,
                "sha256": pdf.sha256,
            },
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        serializer = CertificateSerializer(
            certificate,
            context={"request": request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# PDF Download  (GET /api/certificates/<pk>/pdf/)
# ---------------------------------------------------------------------------

class CertificatePDFDownloadView(APIView):
    """
    GET /api/certificates/<pk>/pdf/

    Securely streams the PostgreSQL-stored PDF for a certificate.

    Access rules:
    - The certificate owner can download their own certificate's PDF.
    - CertiVerify administrators can download any certificate's PDF.
    - Anyone else receives 403 Forbidden.
    - If no PDF is stored, 404 is returned.

    The PDF bytes are served directly from the database — no filesystem
    access, no path traversal risk, no unsafe filename forwarding.
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [OptionalJWTAuthentication]

    def get(self, request, pk):
        certificate = get_object_or_404(
            Certificate.objects.select_related("owner"),
            pk=pk,
        )

        user = request.user

        # Enforce access control
        is_admin = is_certiverify_admin(user)
        is_owner = certificate.owner_id == user.id

        if not (is_admin or is_owner):
            return Response(
                {"detail": "You do not have permission to download this certificate."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Retrieve the PDF stored in PostgreSQL
        try:
            pdf_doc = certificate.pdf_document
        except CertificatePDF.DoesNotExist:
            pdf_doc = None

        if pdf_doc is None:
            # Fallback: if certificate has image file, generate PDF on-the-fly and persist
            if certificate.file and certificate.file.storage.exists(certificate.file.name):
                try:
                    with certificate.file.open("rb") as f:
                        img_bytes = f.read()
                    pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                    buf = io.BytesIO()
                    pil_img.save(buf, format="PDF", resolution=150)
                    pdf_doc = CertificatePDF.store(
                        certificate=certificate,
                        raw_bytes=buf.getvalue(),
                        filename=f"{certificate.certificate_number}.pdf",
                    )
                except Exception as exc:
                    logger.warning("Could not auto-generate PDF for certificate %s: %s", certificate.pk, exc)

        if pdf_doc is None:
            return Response(
                {"detail": "No PDF is stored for this certificate."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Build a safe download filename — never trust user-supplied names
        safe_cert_num = "".join(
            c for c in certificate.certificate_number if c.isalnum() or c in "-_"
        )
        download_filename = f"certificate_{safe_cert_num}.pdf"

        # Return raw bytes with correct headers
        response = HttpResponse(
            bytes(pdf_doc.content),
            content_type="application/pdf",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{download_filename}"'
        )
        response["Content-Length"] = pdf_doc.file_size
        response["X-Content-Type-Options"] = "nosniff"
        return response


# ---------------------------------------------------------------------------
# Course Views
# ---------------------------------------------------------------------------

class CourseListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/certificates/courses/ — list courses
    POST /api/certificates/courses/ — create course (admin only)
    """
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        from rest_framework.exceptions import PermissionDenied
        if not is_certiverify_admin(self.request.user):
            raise PermissionDenied("Only administrators can create courses.")
        serializer.save(created_by=self.request.user)


class CourseHasProtectedRecords(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = (
        "This course is linked to certificates or generation history and cannot be deleted. "
        "Those records have been preserved."
    )
    default_code = "course_has_protected_records"


class CourseDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/DELETE /api/certificates/courses/<pk>/
    """
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]

    def perform_update(self, serializer):
        from rest_framework.exceptions import PermissionDenied
        if not is_certiverify_admin(self.request.user):
            raise PermissionDenied("Only administrators can edit courses.")
        serializer.save()

    def perform_destroy(self, instance):
        from rest_framework.exceptions import PermissionDenied
        if not is_certiverify_admin(self.request.user):
            raise PermissionDenied("Only administrators can delete courses.")
        if (
            Certificate.objects.filter(course=instance).exists()
            or GenerationBatch.objects.filter(course=instance).exists()
        ):
            raise CourseHasProtectedRecords()
        instance.delete()


# ---------------------------------------------------------------------------
# Certificate Template Views
# ---------------------------------------------------------------------------

class CertificateTemplateListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/certificates/templates/ — list templates (admin only)
    POST /api/certificates/templates/ — upload template (admin only)
    """
    queryset = CertificateTemplate.objects.all()
    serializer_class = CertificateTemplateSerializer
    permission_classes = [IsAuthenticated, IsCertiVerifyAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def perform_create(self, serializer):
        image_val = serializer.validated_data.get("image")
        fmt = getattr(image_val, "_template_format", "PNG")
        template = serializer.save(uploaded_by=self.request.user, file_format=fmt, version=1)
        log_action(
            action=AuditLog.Action.TEMPLATE_UPLOADED,
            actor=self.request.user,
            target_type="CertificateTemplate",
            target_id=template.id,
            description=f"Uploaded certificate template: {template.name} ({fmt})",
            metadata={"template_name": template.name, "image": str(template.image), "file_format": fmt},
            ip_address=self.request.META.get("REMOTE_ADDR"),
        )


class CertificateTemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/PATCH/DELETE /api/certificates/templates/<pk>/
    """
    queryset = CertificateTemplate.objects.all()
    serializer_class = CertificateTemplateSerializer
    permission_classes = [IsAuthenticated, IsCertiVerifyAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def perform_destroy(self, instance):
        from rest_framework.exceptions import PermissionDenied, ValidationError

        if not is_certiverify_admin(self.request.user):
            raise PermissionDenied("Only administrators can delete templates.")

        batch_count = instance.generation_batches.count()
        cert_count = instance.certificates.count()
        if batch_count > 0 or cert_count > 0:
            raise ValidationError({
                "detail": (
                    f"Cannot delete template '{instance.name}' because it has already been "
                    f"used for {batch_count} certificate generation batch(es) and {cert_count} certificate(s). "
                    f"Templates in use must be preserved to reproduce previously issued certificates."
                )
            })

        template_id = instance.id
        template_name = instance.name
        image_field = instance.image

        instance.delete()

        if image_field and image_field.storage.exists(image_field.name):
            try:
                image_field.storage.delete(image_field.name)
            except Exception as e:
                logger.warning("Failed to delete template file %s: %s", image_field.name, e)

        log_action(
            action=AuditLog.Action.OTHER,
            actor=self.request.user,
            target_type="CertificateTemplate",
            target_id=str(template_id),
            description=f"Deleted unused certificate template: {template_name}",
            ip_address=self.request.META.get("REMOTE_ADDR"),
        )

    def perform_update(self, serializer):
        from rest_framework.exceptions import PermissionDenied
        if not is_certiverify_admin(self.request.user):
            raise PermissionDenied("Only administrators can modify templates.")

        instance = serializer.instance
        new_image = self.request.FILES.get("image")
        batch_count = instance.generation_batches.count()
        cert_count = instance.certificates.count()
        fmt = getattr(serializer.validated_data.get("image"), "_template_format", None)

        create_new_version = (
            self.request.data.get("new_version") in ("true", "1", True)
            or (new_image and (batch_count > 0 or cert_count > 0))
        )
        if create_new_version and new_image:
            # Create a new version of the template to preserve historical reproducibility
            instance.pk = None
            instance.version += 1
            if "(v" in instance.name:
                base_name = instance.name.split("(v")[0].strip()
                instance.name = f"{base_name} (v{instance.version})"
            else:
                instance.name = f"{instance.name} (v{instance.version})"
            if fmt:
                instance.file_format = fmt
            template = serializer.save(uploaded_by=self.request.user)
            log_action(
                action=AuditLog.Action.TEMPLATE_UPLOADED,
                actor=self.request.user,
                target_type="CertificateTemplate",
                target_id=template.id,
                description=f"Created new template version: {template.name}",
                metadata={"template_name": template.name, "version": template.version},
                ip_address=self.request.META.get("REMOTE_ADDR"),
            )
        else:
            if fmt:
                serializer.save(file_format=fmt)
            else:
                serializer.save()


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def parse_date_flexible(val: str, field_name: str = "Date") -> tuple:
    """
    Parses a date string strictly accepting DD/MM/YYYY first, with backward compatibility for YYYY-MM-DD.
    Avoids ambiguous parsing such as interpreting 04/05/2026 as April 5 instead of 4 May.
    Returns (date_obj, None) on success or (None, error_str) on failure.
    """
    if not val or not str(val).strip():
        return None, f"{field_name} is required."
    val_clean = str(val).strip()

    # Try DD/MM/YYYY first
    try:
        dt = datetime.strptime(val_clean, "%d/%m/%Y").date()
        return dt, None
    except ValueError:
        pass

    # Try YYYY-MM-DD next for backward compatibility
    try:
        dt = datetime.strptime(val_clean, "%Y-%m-%d").date()
        return dt, None
    except ValueError:
        pass

    return None, f"{field_name} '{val_clean}' is invalid. Expected format: DD/MM/YYYY (e.g. 24/07/2026)."


def validate_student_name(val: str) -> tuple:
    """
    Validates student recipient name:
    - Trim leading and trailing whitespace
    - Require non-empty
    - Count actual normalized length
    - Accept 1–29 characters
    - Reject 30 or more characters with clear message
    - Never silently truncate
    """
    trimmed = (val or "").strip()
    if not trimmed:
        return None, "Student name is required."
    if len(trimmed) >= 30:
        return None, f"Student name must be 1–29 characters (currently {len(trimmed)} characters: '{trimmed}')."
    return trimmed, None


# ---------------------------------------------------------------------------
# CSV Template Download
# ---------------------------------------------------------------------------

class CSVTemplateDownloadView(APIView):
    """
    GET /api/certificates/generate/csv-template/
    Downloads the CSV template:
    - Default/simple: student_name,student_email
    - Full (?columns=full): student_name,student_email,course_name,start_date,end_date,issue_date
    """
    permission_classes = [AllowAny]
    authentication_classes = [OptionalJWTAuthentication]

    def get(self, request):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        if request.query_params.get("columns") == "full" or request.query_params.get("format") == "full":
            writer.writerow(["student_name", "student_email", "course_name", "start_date", "end_date", "issue_date"])
            writer.writerow(["Kartik Hande", "kartik@example.com", "Node", "24/07/2026", "24/08/2026", "14/10/2026"])
        else:
            writer.writerow(["student_name", "student_email"])
            writer.writerow(["Kartik Hande", "kartik@example.com"])
        response = HttpResponse(buffer.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="certificate_upload_template.csv"'
        return response


# ---------------------------------------------------------------------------
# CSV Validation View
# ---------------------------------------------------------------------------

class ValidateCSVView(APIView):
    """
    POST /api/certificates/generate/validate-csv/
    Simplified: only student_name and student_email are required columns.
    All other fields (course_name, start_date, end_date, issue_date) are
    taken from the selected course and can be optionally overridden per row.
    Supports DD/MM/YYYY (and YYYY-MM-DD), enforces student name max 29 chars,
    and checks registered student email accounts.
    """
    permission_classes = [IsAuthenticated, IsCertiVerifyAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response(
                {"detail": "Please upload a CSV file with field name 'file'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        course_id = request.data.get("course_id")
        selected_course = None
        if course_id:
            try:
                selected_course = Course.objects.get(pk=course_id)
            except (Course.DoesNotExist, ValueError):
                return Response(
                    {"detail": f"Course ID {course_id} does not exist."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Batch-level defaults passed from the UI (editable before generation)
        batch_course_name = (request.data.get("batch_course_name") or "").strip()
        batch_start_date = (request.data.get("batch_start_date") or "").strip()
        batch_end_date = (request.data.get("batch_end_date") or "").strip()
        batch_issue_date = (request.data.get("batch_issue_date") or "").strip()

        # Fall back to selected course values when batch-level defaults are not provided
        if selected_course:
            if not batch_course_name:
                batch_course_name = selected_course.name
            if not batch_start_date and selected_course.start_date:
                batch_start_date = selected_course.start_date.strftime("%d/%m/%Y")
            if not batch_end_date and selected_course.end_date:
                batch_end_date = selected_course.end_date.strftime("%d/%m/%Y")
            if not batch_issue_date:
                batch_issue_date = timezone.now().date().strftime("%d/%m/%Y")

        try:
            content = upload.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            upload.seek(0)
            try:
                content = upload.read().decode("latin-1")
            except Exception as e:
                return Response(
                    {"detail": f"Could not read CSV file: {e}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Use newline="" so Python's CSV parser can correctly handle CRLF/LF
        # line endings and quoted fields that contain embedded newlines.
        reader = csv.DictReader(io.StringIO(content, newline=""))
        try:
            fieldnames = reader.fieldnames
        except csv.Error as exc:
            logger.warning("Invalid CSV header uploaded for validation: %s", exc)
            return Response(
                {
                    "detail": (
                        "The CSV format is invalid. Please download the CSV template "
                        "and upload a correctly formatted CSV file."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not fieldnames:
            return Response(
                {"detail": "CSV file is empty or has no header row."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        field_map = {fn.strip().lower(): fn for fn in fieldnames if fn}

        # Only student_name and student_email are strictly required columns.
        # Other fields are optional per-row overrides.
        required_fields = ["student_name", "student_email"]
        optional_fields = ["course_name", "start_date", "end_date", "issue_date"]

        missing_fields = [rf for rf in required_fields if rf not in field_map]
        if missing_fields:
            return Response(
                {
                    "detail": f"CSV is missing required columns: {', '.join(missing_fields)}. Only student_name and student_email are required.",
                    "missing_columns": missing_fields,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        rows_result = []
        seen_emails_in_csv = set()
        valid_count = 0
        invalid_count = 0

        for row_idx, raw_row in enumerate(reader, start=2):
            # Read required fields
            student_name_raw = (raw_row.get(field_map.get("student_name", ""), "") or "").strip()
            student_email_raw = (raw_row.get(field_map.get("student_email", ""), "") or "").strip()

            # Read optional per-row overrides; fall back to batch/course defaults
            def _row_opt(key, batch_default):
                if key in field_map:
                    val = (raw_row.get(field_map[key], "") or "").strip()
                    return val if val else batch_default
                return batch_default

            cname = _row_opt("course_name", batch_course_name)
            start_date_str = _row_opt("start_date", batch_start_date)
            end_date_str = _row_opt("end_date", batch_end_date)
            issue_date_str = _row_opt("issue_date", batch_issue_date)

            errors = []

            # 1. Student name validation (1–29 chars, reject 30+)
            clean_name, name_err = validate_student_name(student_name_raw)
            if name_err:
                errors.append(f"Row {row_idx}: {name_err}")
            else:
                student_name_raw = clean_name

            # 2. Student email & registered user lookup
            email = student_email_raw.lower()
            user_id = None
            has_account = False
            if not email:
                errors.append("Student email is required.")
            elif "@" not in email or "." not in email.split("@")[-1]:
                errors.append(f"Invalid email format: '{student_email_raw}'.")
            else:
                user = User.objects.filter(email__iexact=email).first()
                if user:
                    user_id = user.id
                    has_account = True
                    if not user.is_active:
                        errors.append(f"Student account '{student_email_raw}' is inactive.")

                if email in seen_emails_in_csv:
                    errors.append(f"Duplicate email '{student_email_raw}' found multiple times in this CSV.")
                else:
                    seen_emails_in_csv.add(email)

            # 3. Course name (from batch default; already resolved above)
            if not cname:
                errors.append("Course name is missing. Please select a course before uploading.")

            # 4. Dates validation (DD/MM/YYYY preferred, YYYY-MM-DD accepted)
            parsed_dates = {}
            for date_key, dval in (("start_date", start_date_str), ("end_date", end_date_str), ("issue_date", issue_date_str)):
                d_obj, d_err = parse_date_flexible(dval, date_key.replace("_", " ").capitalize())
                if d_err:
                    errors.append(d_err)
                else:
                    parsed_dates[date_key] = d_obj

            if "start_date" in parsed_dates and "end_date" in parsed_dates:
                if parsed_dates["end_date"] < parsed_dates["start_date"]:
                    errors.append(f"Row {row_idx}: End date cannot be earlier than start date.")

            # Format dates in DD/MM/YYYY for UI display
            disp_start = parsed_dates["start_date"].strftime("%d/%m/%Y") if "start_date" in parsed_dates else start_date_str
            disp_end = parsed_dates["end_date"].strftime("%d/%m/%Y") if "end_date" in parsed_dates else end_date_str
            disp_issue = parsed_dates["issue_date"].strftime("%d/%m/%Y") if "issue_date" in parsed_dates else issue_date_str

            # 5. Check duplicate certificate
            if cname and email:
                dup_qs = Certificate.objects.filter(course_name__iexact=cname)
                if user_id:
                    dup_qs = dup_qs.filter(models.Q(owner_id=user_id) | models.Q(recipient_email__iexact=email))
                else:
                    dup_qs = dup_qs.filter(recipient_email__iexact=email)

                if dup_qs.exists():
                    errors.append(f"A certificate for '{cname}' has already been issued to this student.")

            is_valid = len(errors) == 0
            if is_valid:
                valid_count += 1
            else:
                invalid_count += 1

            rows_result.append({
                "row_number": row_idx,
                "student_name": student_name_raw,
                "student_email": student_email_raw,
                "course_name": cname,
                "start_date": disp_start,
                "end_date": disp_end,
                "issue_date": disp_issue,
                "user_id": user_id,
                "has_account": has_account,
                "is_valid": is_valid,
                "errors": errors,
            })

        log_action(
            action=AuditLog.Action.CSV_VALIDATED,
            actor=request.user,
            target_type="GenerationBatch",
            target_id="",
            description=f"CSV validated: {len(rows_result)} total rows, {valid_count} valid, {invalid_count} invalid",
            metadata={
                "total_rows": len(rows_result),
                "valid_count": valid_count,
                "invalid_count": invalid_count,
            },
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        return Response({
            "total_rows": len(rows_result),
            "valid_rows_count": valid_count,
            "invalid_rows_count": invalid_count,
            "is_valid": invalid_count == 0,
            "rows": rows_result,
            # Return resolved batch defaults so the UI can display them
            "batch_defaults": {
                "course_name": batch_course_name,
                "start_date": batch_start_date,
                "end_date": batch_end_date,
                "issue_date": batch_issue_date,
            },
        })


# ---------------------------------------------------------------------------
# Bulk Generation View
# ---------------------------------------------------------------------------

class BulkGenerateView(APIView):
    """
    POST /api/certificates/generate/bulk/
    Generates personalized certificates in bulk for validated rows.
    """
    permission_classes = [IsAuthenticated, IsCertiVerifyAdmin]

    def post(self, request):
        course_id = request.data.get("course_id")
        template_id = request.data.get("template_id")
        rows = request.data.get("rows", [])

        if not course_id:
            return Response({"detail": "course_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not template_id:
            return Response({"detail": "template_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not rows or not isinstance(rows, list):
            return Response({"detail": "rows list is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            course = Course.objects.get(pk=course_id)
        except (Course.DoesNotExist, ValueError):
            return Response({"detail": f"Course ID {course_id} not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            template = CertificateTemplate.objects.get(pk=template_id)
        except (CertificateTemplate.DoesNotExist, ValueError):
            return Response({"detail": f"Template ID {template_id} not found."}, status=status.HTTP_404_NOT_FOUND)

        if not template.image or not template.image.storage.exists(template.image.name):
            return Response({"detail": "Template image file is missing from storage."}, status=status.HTTP_400_BAD_REQUEST)

        # Create batch record
        batch = GenerationBatch.objects.create(
            course=course,
            template=template,
            status=GenerationBatch.Status.PROCESSING,
            total_rows=len(rows),
            created_by=request.user,
        )

        error_report = []
        successful_count = 0
        failed_count = 0
        skipped_duplicates = 0
        emails_sent = 0
        emails_failed = 0

        batch_course_name = (request.data.get("course_name") or "").strip() or course.name
        batch_title = (request.data.get("certificate_title") or "").strip() or course.title or "Certificate of Completion"
        batch_issuer = (request.data.get("issuer") or "").strip() or course.issuer or "OneSmarter, Inc."
        batch_description = (request.data.get("completion_description") or "").strip()

        layout_settings = dict(template.layout_config or {})
        shared_field_values = request.data.get("field_values", {})
        if isinstance(shared_field_values, dict):
            saved_field_values = dict(layout_settings.get("field_values", {}))
            saved_field_values.update(shared_field_values)
            layout_settings["field_values"] = saved_field_values

        # Decode the batch's template only once; each rendering call draws on its
        # own copy, so recipient text cannot leak into another recipient's image.
        try:
            template_background = load_template_image(template.image.path)
        except Exception:
            logger.exception("Could not load template image for batch %s", batch.id)
            batch.status = GenerationBatch.Status.FAILED
            batch.failed = len(rows)
            batch.error_report = [{
                "row_number": (row.get("row_number", index + 1) if isinstance(row, dict) else index + 1),
                "student_name": (row.get("student_name", "") if isinstance(row, dict) else ""),
                "student_email": (row.get("student_email", "") if isinstance(row, dict) else ""),
                "error": "Template image could not be loaded; see the server log for details.",
            } for index, row in enumerate(rows)]
            batch.completed_at = timezone.now()
            batch.save(update_fields=["status", "failed", "error_report", "completed_at"])
            return Response(GenerationBatchSerializer(batch).data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        for r in rows:
            student_email = (r.get("student_email") or "").strip().lower()
            raw_student_name = (r.get("student_name") or "").strip()
            start_date_str = (r.get("start_date") or "").strip()
            end_date_str = (r.get("end_date") or "").strip()
            issue_date_str = (r.get("issue_date") or "").strip()
            course_name = (r.get("course_name") or "").strip() or batch_course_name
            cert_title = (r.get("certificate_title") or "").strip() or batch_title
            issuer_name = (r.get("issuer") or "").strip() or batch_issuer
            desc = (r.get("completion_description") or "").strip() or batch_description
            row_num = r.get("row_number", "?")

            # Validate student name length (1-29 chars)
            student_name, name_err = validate_student_name(raw_student_name)
            if name_err:
                failed_count += 1
                error_report.append({
                    "row_number": row_num,
                    "student_name": raw_student_name,
                    "student_email": student_email,
                    "error": name_err,
                })
                continue

            # Lookup student (optional for unregistered recipients)
            user = User.objects.filter(email__iexact=student_email).first()

            # Duplicate check
            dup_qs = Certificate.objects.filter(course_name__iexact=course_name)
            if user:
                dup_qs = dup_qs.filter(models.Q(owner=user) | models.Q(recipient_email__iexact=student_email))
            else:
                dup_qs = dup_qs.filter(recipient_email__iexact=student_email)

            if dup_qs.exists():
                skipped_duplicates += 1
                error_report.append({
                    "row_number": row_num,
                    "student_name": student_name,
                    "student_email": student_email,
                    "error": f"Duplicate certificate already exists for '{course_name}'. Skipped.",
                })
                continue

            # Parse dates strictly (DD/MM/YYYY first, YYYY-MM-DD compatible)
            start_date, s_err = parse_date_flexible(start_date_str, "Start date")
            end_date, e_err = parse_date_flexible(end_date_str, "End date")
            issue_date, i_err = parse_date_flexible(issue_date_str, "Issue date")

            date_err = s_err or e_err or i_err
            if not date_err and end_date < start_date:
                date_err = "End date cannot be earlier than start date."

            if date_err:
                failed_count += 1
                error_report.append({
                    "row_number": row_num,
                    "student_name": student_name,
                    "student_email": student_email,
                    "error": date_err,
                })
                continue

            # Generate unique certificate number
            year = issue_date.year
            cert_num = f"OSCV-{year}-{uuid.uuid4().hex[:8].upper()}"
            while Certificate.objects.filter(certificate_number=cert_num).exists():
                cert_num = f"OSCV-{year}-{uuid.uuid4().hex[:8].upper()}"

            try:
                row_layout = dict(layout_settings)
                row_fields = dict(layout_settings.get("field_values", {}))
                custom_fields = r.get("custom_fields", {})
                if isinstance(custom_fields, dict):
                    row_fields.update(custom_fields)
                row_layout["field_values"] = row_fields
                missing_fields = _missing_template_fields(
                    template,
                    {
                        "student_name": student_name,
                        "certificate_number": cert_num,
                        "course_name": course_name,
                        "start_date": start_date.strftime("%d/%m/%Y"),
                        "end_date": end_date.strftime("%d/%m/%Y"),
                        "issue_date": issue_date.strftime("%d/%m/%Y"),
                        "completion_description": desc,
                        "issuer": issuer_name,
                    },
                    row_fields,
                )
                if missing_fields:
                    raise ValueError("Missing values for configured template field(s): " + ", ".join(missing_fields))
                png_bytes, sha256_hex = generate_certificate_image(
                    template_path=template.image.path,
                    template_image=template_background,
                    student_name=student_name,
                    course_name=course_name,
                    start_date=start_date.strftime("%d/%m/%Y"),
                    end_date=end_date.strftime("%d/%m/%Y"),
                    issue_date=issue_date.strftime("%d/%m/%Y"),
                    certificate_number=cert_num,
                    issuer_name=issuer_name,
                    completion_description=desc,
                    layout_overrides=row_layout,
                )

                with transaction.atomic():
                    cert = Certificate(
                        owner=user,
                        recipient_email=student_email,
                        title=cert_title,
                        issuer=issuer_name,
                        certificate_number=cert_num,
                        recipient_name=student_name,
                        issue_date=issue_date,
                        course=course,
                        course_name=course_name,
                        template=template,
                        completion_description=desc,
                        start_date=start_date,
                        end_date=end_date,
                        generation_batch=batch,
                        file_sha256=sha256_hex,
                        status=Certificate.Status.VERIFIED,
                    )
                    cert.file.save(f"{cert_num}.png", ContentFile(png_bytes), save=False)
                    cert.save()

                    # Convert PNG bytes to PDF and store persistently in PostgreSQL
                    try:
                        img_for_pdf = Image.open(io.BytesIO(png_bytes)).convert("RGB")
                        pdf_buffer = io.BytesIO()
                        img_for_pdf.save(pdf_buffer, format="PDF", resolution=150)
                        CertificatePDF.store(
                            certificate=cert,
                            raw_bytes=pdf_buffer.getvalue(),
                            filename=f"{cert_num}.pdf",
                        )
                    except Exception as pdf_err:
                        logger.warning("Failed to generate/store PDF for cert %s: %s", cert_num, pdf_err)

                    # In-app notification only if user account exists
                    if user:
                        Notification.objects.create(
                            recipient=user,
                            notification_type=Notification.NotificationType.CERTIFICATE_CREATED,
                            title=f"New Certificate Issued: {course_name}",
                            message=f"Your certificate ({cert_num}) for {course_name} has been issued and is available in My Certificates.",
                            certificate=cert,
                        )

                # Send email notification outside atomic transaction
                email_ok, email_err = _send_and_record_certificate_email(cert)

                if email_ok:
                    emails_sent += 1
                else:
                    emails_failed += 1

                successful_count += 1

            except Exception as exc:
                logger.exception("Failed to generate certificate for %s", student_email)
                failed_count += 1
                error_report.append({
                    "row_number": row_num,
                    "student_name": student_name,
                    "student_email": student_email,
                    "error": (
                        str(exc)
                        if isinstance(exc, ValueError)
                        else "Certificate rendering or storage failed; see the server log for details."
                    ),
                })

        # Finalize batch
        batch.successful = successful_count
        batch.failed = failed_count
        batch.skipped_duplicates = skipped_duplicates
        batch.emails_sent = emails_sent
        batch.emails_failed = emails_failed
        batch.error_report = error_report
        batch.status = (
            GenerationBatch.Status.COMPLETED
            if successful_count > 0 or len(rows) == 0
            else GenerationBatch.Status.FAILED
        )
        batch.completed_at = timezone.now()
        batch_save_warning = None
        try:
            batch.save()
        except Exception:
            logger.exception("Batch %s generated but its final summary could not be saved", batch.id)
            batch_save_warning = "Certificates were generated, but the batch summary could not be saved."

        response_data = GenerationBatchSerializer(batch).data
        if batch_save_warning:
            response_data["warning"] = batch_save_warning
        try:
            log_action(
                action=AuditLog.Action.BATCH_GENERATED,
                actor=request.user,
                target_type="GenerationBatch",
                target_id=batch.id,
                description=f"Batch #{batch.id} generated: {successful_count} created, {failed_count} failed, {skipped_duplicates} skipped",
                metadata={
                    "batch_id": batch.id,
                    "course_id": course.id,
                    "template_id": template.id,
                    "successful": successful_count,
                    "failed": failed_count,
                    "skipped_duplicates": skipped_duplicates,
                    "emails_sent": emails_sent,
                    "emails_failed": emails_failed,
                },
                ip_address=request.META.get("REMOTE_ADDR"),
            )
        except Exception:
            logger.exception("Batch %s generated but its audit entry could not be written", batch.id)
            response_data["warning"] = "; ".join(filter(None, [response_data.get("warning"), "Batch generated; the audit entry could not be recorded."]))

        return Response(response_data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Single Certificate Generation View
# ---------------------------------------------------------------------------

class SingleGenerateView(APIView):
    """
    POST /api/certificates/generate/single/
    Generates a single personalized certificate manually without CSV.
    """
    permission_classes = [IsAuthenticated, IsCertiVerifyAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        course_id = request.data.get("course_id")
        template_id = request.data.get("template_id")
        template_file = request.FILES.get("template_file") or request.FILES.get("image")
        user_id = request.data.get("user_id") or request.data.get("owner_id")
        student_email = (request.data.get("student_email") or "").strip().lower()
        raw_student_name = (request.data.get("student_name") or "").strip()
        start_date_str = (request.data.get("start_date") or "").strip()
        end_date_str = (request.data.get("end_date") or "").strip()
        issue_date_str = (request.data.get("issue_date") or "").strip()

        if not course_id:
            return Response({"detail": "Course is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Support selecting existing template OR uploading a new template directly
        template = None
        if not template_id and template_file:
            tpl_name = (request.data.get("template_name") or template_file.name or "Uploaded Template").strip()
            tpl_desc = (request.data.get("template_description") or request.data.get("completion_description") or "").strip()
            tpl_serializer = CertificateTemplateSerializer(
                data={"name": tpl_name, "image": template_file, "description": tpl_desc},
                context={"request": request},
            )
            tpl_serializer.is_valid(raise_exception=True)
            fmt = getattr(tpl_serializer.validated_data.get("image"), "_template_format", "PNG")
            template = tpl_serializer.save(uploaded_by=request.user, file_format=fmt, version=1)
            template_id = template.id
        elif not template_id:
            return Response({"detail": "Certificate template or template file is required."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            try:
                template = CertificateTemplate.objects.get(pk=template_id)
            except (CertificateTemplate.DoesNotExist, ValueError):
                return Response({"detail": "Selected template not found."}, status=status.HTTP_404_NOT_FOUND)

        if not (user_id or student_email):
            return Response({"detail": "Student recipient email is required."}, status=status.HTTP_400_BAD_REQUEST)

        if student_email and ("@" not in student_email or "." not in student_email.split("@")[-1]):
            return Response({"detail": f"Invalid email format: '{student_email}'."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate student name length (1-29 chars)
        student_name, name_err = validate_student_name(raw_student_name)
        if name_err:
            return Response({"detail": name_err, "student_name": name_err}, status=status.HTTP_400_BAD_REQUEST)

        try:
            course = Course.objects.get(pk=course_id)
        except (Course.DoesNotExist, ValueError):
            return Response({"detail": "Selected course not found."}, status=status.HTTP_404_NOT_FOUND)

        # The selected course is authoritative for course dates; issuance defaults
        # to today when the administrator did not explicitly provide a date.
        start_date_str = start_date_str or course.start_date.strftime("%Y-%m-%d")
        end_date_str = end_date_str or course.end_date.strftime("%Y-%m-%d")
        issue_date_str = issue_date_str or timezone.localdate().strftime("%Y-%m-%d")

        if not template.image or not template.image.storage.exists(template.image.name):
            return Response({"detail": "Template image file is missing from storage."}, status=status.HTTP_400_BAD_REQUEST)

        # Lookup student user (optional — unregistered recipients supported)
        user = None
        if user_id:
            user = User.objects.filter(pk=user_id).first()
        if not user and student_email:
            user = User.objects.filter(email__iexact=student_email).first()
        if user and not student_email:
            student_email = user.email.lower()

        course_name = (request.data.get("course_name") or "").strip() or course.name
        certificate_title = (request.data.get("certificate_title") or "").strip() or course.title or "Certificate of Completion"
        issuer_name = (request.data.get("issuer") or "").strip() or course.issuer or "OneSmarter, Inc."
        
        # The template description is metadata. Dynamic text belongs in the saved layout,
        # or in an explicit generation override, to avoid printing it over static artwork.
        completion_description = (request.data.get("completion_description") or "").strip()

        # Formatting is taken only from the saved administrator-managed template.
        layout_settings = dict(template.layout_config or {})
        shared_field_values = request.data.get("field_values", {})
        if isinstance(shared_field_values, dict):
            saved_field_values = dict(layout_settings.get("field_values", {}))
            saved_field_values.update(shared_field_values)
            layout_settings["field_values"] = saved_field_values

        # Check duplicate & reissue rules
        dup_qs = Certificate.objects.filter(course_name__iexact=course_name)
        if user:
            dup_qs = dup_qs.filter(models.Q(owner=user) | models.Q(recipient_email__iexact=student_email))
        else:
            dup_qs = dup_qs.filter(recipient_email__iexact=student_email)
        existing_cert = dup_qs.first()
        reissue = request.data.get("reissue") in (True, "true", "1")
        if existing_cert and not reissue:
            return Response({
                "detail": f"A certificate for '{course_name}' has already been issued to this student.",
                "existing_certificate_number": existing_cert.certificate_number,
                "can_reissue": True,
            }, status=status.HTTP_400_BAD_REQUEST)

        # Parse dates (DD/MM/YYYY or YYYY-MM-DD)
        start_date, s_err = parse_date_flexible(start_date_str, "Start date")
        end_date, e_err = parse_date_flexible(end_date_str, "End date")
        issue_date, i_err = parse_date_flexible(issue_date_str, "Issue date")

        date_err = s_err or e_err or i_err
        if date_err:
            return Response({"detail": date_err}, status=status.HTTP_400_BAD_REQUEST)

        if end_date < start_date:
            return Response({"detail": "End date cannot be earlier than start date."}, status=status.HTTP_400_BAD_REQUEST)

        missing_fields = _missing_template_fields(
            template,
            {
                "student_name": student_name,
                "certificate_number": "OSCV-PREVIEW-000000",
                "course_name": course_name,
                "start_date": start_date.strftime("%d/%m/%Y"),
                "end_date": end_date.strftime("%d/%m/%Y"),
                "issue_date": issue_date.strftime("%d/%m/%Y"),
                "completion_description": completion_description,
                "issuer": issuer_name,
            },
            layout_settings.get("field_values", {}),
        )
        if missing_fields:
            return Response(
                {"detail": "Missing values for configured template field(s): " + ", ".join(missing_fields)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Unique certificate number
        year = issue_date.year
        cert_num = f"OSCV-{year}-{uuid.uuid4().hex[:8].upper()}"
        while Certificate.objects.filter(certificate_number=cert_num).exists():
            cert_num = f"OSCV-{year}-{uuid.uuid4().hex[:8].upper()}"

        try:
            png_bytes, sha256_hex = generate_certificate_image(
                template_path=template.image.path,
                student_name=student_name,
                course_name=course_name,
                start_date=start_date.strftime("%d/%m/%Y"),
                end_date=end_date.strftime("%d/%m/%Y"),
                issue_date=issue_date.strftime("%d/%m/%Y"),
                certificate_number=cert_num,
                issuer_name=issuer_name,
                completion_description=completion_description,
                layout_overrides=layout_settings,
            )

            with transaction.atomic():
                cert = Certificate(
                    owner=user,
                    recipient_email=student_email,
                    title=certificate_title,
                    issuer=issuer_name,
                    certificate_number=cert_num,
                    recipient_name=student_name,
                    issue_date=issue_date,
                    course=course,
                    course_name=course_name,
                    template=template,
                    completion_description=completion_description,
                    start_date=start_date,
                    end_date=end_date,
                    file_sha256=sha256_hex,
                    status=Certificate.Status.VERIFIED,
                )
                cert.file.save(f"{cert_num}.png", ContentFile(png_bytes), save=False)
                cert.save()

                # Convert PNG bytes to PDF and store persistently in PostgreSQL
                try:
                    img_for_pdf = Image.open(io.BytesIO(png_bytes)).convert("RGB")
                    pdf_buffer = io.BytesIO()
                    img_for_pdf.save(pdf_buffer, format="PDF", resolution=150)
                    CertificatePDF.store(
                        certificate=cert,
                        raw_bytes=pdf_buffer.getvalue(),
                        filename=f"{cert_num}.pdf",
                    )
                except Exception as pdf_err:
                    logger.warning("Failed to generate/store PDF for single cert %s: %s", cert_num, pdf_err)

                if user:
                    Notification.objects.create(
                        recipient=user,
                        notification_type=Notification.NotificationType.CERTIFICATE_CREATED,
                        title=f"New Certificate Issued: {course_name}",
                        message=f"Your certificate ({cert_num}) for {course_name} has been issued and is available in My Certificates.",
                        certificate=cert,
                    )

            # Send email
            email_ok, email_err = _send_and_record_certificate_email(cert)

            action_type = AuditLog.Action.CERTIFICATE_REISSUED if existing_cert else AuditLog.Action.CERTIFICATE_GENERATED
            audit_warning = None
            try:
                log_action(
                    action=action_type,
                    actor=request.user,
                    target_type="Certificate",
                    target_id=cert.id,
                    description=f"{'Reissued' if existing_cert else 'Generated'} single certificate {cert_num} for {user.username if user else student_email} ({course_name})",
                    metadata={
                        "certificate_number": cert_num,
                        "student_name": student_name,
                        "student_id": user.id if user else None,
                        "recipient_email": student_email,
                        "course_id": course.id,
                        "template_id": template.id,
                        "email_sent": email_ok,
                        "reissue": bool(existing_cert),
                    },
                    ip_address=request.META.get("REMOTE_ADDR"),
                )
            except Exception:
                logger.exception("Certificate %s generated but its audit entry could not be written", cert_num)
                audit_warning = "Certificate generated; the audit entry could not be recorded."

            serializer = CertificateSerializer(cert, context={"request": request})
            response_data = serializer.data
            if audit_warning:
                response_data["warning"] = audit_warning
            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as exc:
            logger.exception("Failed to generate single certificate")
            return Response({"detail": "Certificate generation failed. Check the server log for diagnostic details."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Certificate Preview View
# ---------------------------------------------------------------------------

class PreviewCertificateView(APIView):
    """
    POST /api/certificates/generate/preview/
    Generates an in-memory preview of the personalized certificate image.
    Returns base64 data URL with DD/MM/YYYY date formatting.
    """
    permission_classes = [IsAuthenticated, IsCertiVerifyAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        template_id = request.data.get("template_id")
        course_id = request.data.get("course_id")
        template_file = request.FILES.get("template_file") or request.FILES.get("image")
        student_name = (request.data.get("student_name") or "John Doe").strip()
        course_name = (request.data.get("course_name") or "").strip()
        start_date_str = (request.data.get("start_date") or "").strip()
        end_date_str = (request.data.get("end_date") or "").strip()
        issue_date_str = (request.data.get("issue_date") or "").strip()
        issuer_name = (request.data.get("issuer_name") or request.data.get("issuer") or "").strip()

        course = None
        if course_id:
            try:
                course = Course.objects.get(pk=course_id)
            except (Course.DoesNotExist, ValueError):
                return Response({"detail": "Selected course not found."}, status=status.HTTP_404_NOT_FOUND)
        if course:
            course_name = course_name or course.name
            start_date_str = start_date_str or course.start_date.strftime("%Y-%m-%d")
            end_date_str = end_date_str or course.end_date.strftime("%Y-%m-%d")
            issuer_name = issuer_name or course.issuer
        issuer_name = issuer_name or "OneSmarter, Inc."

        template = None
        if not template_id and template_file:
            tpl_name = (request.data.get("template_name") or template_file.name or "Preview Template").strip()
            tpl_desc = (request.data.get("template_description") or request.data.get("completion_description") or "").strip()
            tpl_serializer = CertificateTemplateSerializer(
                data={"name": tpl_name, "image": template_file, "description": tpl_desc},
                context={"request": request},
            )
            tpl_serializer.is_valid(raise_exception=True)
            fmt = getattr(tpl_serializer.validated_data.get("image"), "_template_format", "PNG")
            template = tpl_serializer.save(uploaded_by=request.user, file_format=fmt, version=1)
            template_id = template.id
        elif not template_id:
            return Response({"detail": "template_id or template_file is required."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            try:
                template = CertificateTemplate.objects.get(pk=template_id)
            except (CertificateTemplate.DoesNotExist, ValueError):
                return Response({"detail": "Template not found."}, status=status.HTTP_404_NOT_FOUND)

        if not template.image or not template.image.storage.exists(template.image.name):
            return Response({"detail": "Template image file missing from storage."}, status=status.HTTP_400_BAD_REQUEST)

        completion_description = (request.data.get("completion_description") or "").strip()

        layout_settings = dict(template.layout_config or {})
        shared_field_values = request.data.get("field_values", {})
        if isinstance(shared_field_values, dict):
            saved_field_values = dict(layout_settings.get("field_values", {}))
            saved_field_values.update(shared_field_values)
            layout_settings["field_values"] = saved_field_values

        # Preview uses course dates when available, leaves unresolved optional dates blank,
        # and uses the real current date for the system-generated issue date.
        start_date, start_err = parse_date_flexible(start_date_str, "Start date") if start_date_str else (None, None)
        end_date, end_err = parse_date_flexible(end_date_str, "End date") if end_date_str else (None, None)
        issue_date, issue_err = parse_date_flexible(issue_date_str, "Issue date") if issue_date_str else (timezone.localdate(), None)
        date_err = start_err or end_err or issue_err
        if date_err:
            return Response({"detail": date_err}, status=status.HTTP_400_BAD_REQUEST)
        if start_date and end_date and end_date < start_date:
            return Response({"detail": "End date cannot be earlier than start date."}, status=status.HTTP_400_BAD_REQUEST)

        start_disp = start_date.strftime("%d/%m/%Y") if start_date else ""
        end_disp = end_date.strftime("%d/%m/%Y") if end_date else ""
        issue_disp = issue_date.strftime("%d/%m/%Y")
        field_values = layout_settings.get("field_values", {})
        missing_fields = _missing_template_fields(template, {
            "student_name": student_name,
            "certificate_number": "OSCV-PREVIEW-000000",
            "course_name": course_name,
            "start_date": start_disp,
            "end_date": end_disp,
            "issue_date": issue_disp,
            "completion_description": completion_description,
            "issuer": issuer_name,
        }, field_values)
        if missing_fields:
            return Response({"detail": "Missing values for configured template field(s): " + ", ".join(missing_fields)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            png_bytes, sha256_hex = generate_certificate_image(
                template_path=template.image.path,
                student_name=student_name,
                course_name=course_name,
                start_date=start_disp,
                end_date=end_disp,
                issue_date=issue_disp,
                certificate_number="OSCV-PREVIEW-000000",
                issuer_name=issuer_name,
                completion_description=completion_description,
                layout_overrides=layout_settings,
            )
            b64_str = base64.b64encode(png_bytes).decode("ascii")
            return Response({
                "preview_url": f"data:image/png;base64,{b64_str}",
                "file_size": len(png_bytes),
                "sha256": sha256_hex,
            })
        except Exception as exc:
            logger.exception("Failed generating preview certificate")
            return Response({"detail": "Could not generate preview. Check the server log for details."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Batch List & Detail Views
# ---------------------------------------------------------------------------

class BatchListView(generics.ListAPIView):
    """
    GET /api/certificates/generate/batches/ — list all generation batches
    """
    queryset = GenerationBatch.objects.select_related("course", "template", "created_by").all()
    serializer_class = GenerationBatchSerializer
    permission_classes = [IsAuthenticated, IsCertiVerifyAdmin]


class BatchDetailView(generics.RetrieveAPIView):
    """
    GET /api/certificates/generate/batches/<pk>/ — batch results and error report
    """
    queryset = GenerationBatch.objects.select_related("course", "template", "created_by").all()
    serializer_class = GenerationBatchSerializer
    permission_classes = [IsAuthenticated, IsCertiVerifyAdmin]


# ---------------------------------------------------------------------------
# Retry Email View
# ---------------------------------------------------------------------------

class RetryEmailView(APIView):
    """
    POST /api/certificates/<pk>/retry-email/
    Retries sending the certificate email notification.
    """
    permission_classes = [IsAuthenticated, IsCertiVerifyAdmin]

    def post(self, request, pk):
        with transaction.atomic():
            cert = get_object_or_404(
                Certificate.objects.select_for_update().select_related("owner", "course"), pk=pk
            )

            if cert.email_sent:
                return Response({
                    "success": True,
                    "email_sent": True,
                    "message": "Certificate email was already accepted by the mail backend; no duplicate was sent.",
                }, status=status.HTTP_200_OK)

            email_ok, email_err = _send_and_record_certificate_email(cert)

        log_action(
            action=AuditLog.Action.EMAIL_RETRY,
            actor=request.user,
            target_type="Certificate",
            target_id=cert.id,
            description=f"Email notification retry for {cert.certificate_number}: {'Success' if email_ok else 'Failed'}",
            metadata={
                "certificate_number": cert.certificate_number,
                "recipient_email": cert.owner.email if cert.owner else "",
                "success": email_ok,
                "error": email_err,
            },
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        return Response({
            "success": email_ok,
            "email_sent": email_ok,
            "email_error": email_err,
            "message": "Email sent successfully." if email_ok else f"Email failed: {email_err}",
        })


# ---------------------------------------------------------------------------
# Certificate Image View (Stream generated PNG)
# ---------------------------------------------------------------------------

class CertificateImageView(APIView):
    """
    GET /api/certificates/<pk>/image/
    Serves the personalized certificate image.
    Accessible only to certificate owner or CertiVerify administrator.
    Uses normal JWT Bearer authentication; credentials are never accepted in query strings.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [OptionalJWTAuthentication]

    def get(self, request, pk):
        cert = get_object_or_404(Certificate.objects.select_related("owner"), pk=pk)

        user = request.user

        is_admin = is_certiverify_admin(user)
        is_owner = cert.owner_id == user.id

        if not (is_admin or is_owner):
            return Response(
                {"detail": "You do not have permission to view this certificate image."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not cert.file:
            return Response(
                {"detail": "No image is stored for this certificate.", "missing_file": True},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            if not cert.file.storage.exists(cert.file.name):
                return Response(
                    {"detail": "Certificate file is missing from storage.", "missing_file": True},
                    status=status.HTTP_404_NOT_FOUND,
                )

            with cert.file.open("rb") as f:
                raw_bytes = f.read()

            target_fmt = request.query_params.get("format", "").lower()
            if target_fmt in ("jpeg", "jpg"):
                try:
                    pil_img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
                    buf = io.BytesIO()
                    pil_img.save(buf, format="JPEG", quality=95)
                    raw_bytes = buf.getvalue()
                    content_type = "image/jpeg"
                except Exception:
                    content_type = "image/png"
            elif cert.file.name.lower().endswith((".jpg", ".jpeg")):
                content_type = "image/jpeg"
            else:
                content_type = "image/png"

            response = HttpResponse(raw_bytes, content_type=content_type)
            if request.query_params.get("download", "").lower() in ("true", "1"):
                safe_cert_num = "".join(c for c in cert.certificate_number if c.isalnum() or c in "-_")
                ext = "jpg" if "jpeg" in content_type else "png"
                response["Content-Disposition"] = f'attachment; filename="certificate_{safe_cert_num}.{ext}"'
            response["Content-Length"] = len(raw_bytes)
            response["X-Content-Type-Options"] = "nosniff"
            return response
        except Exception as exc:
            logger.exception("Failed to open certificate file %s: %s", cert.pk, exc)
            return Response({"detail": "Certificate image file could not be read.", "missing_file": True}, status=status.HTTP_404_NOT_FOUND)
