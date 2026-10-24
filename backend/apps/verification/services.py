"""Shared, status-aware public certificate verification rules."""

import hashlib
import hmac

from apps.certificates.models import Certificate, CertificatePDF
from apps.audit.models import AuditLog
from apps.audit.services import log_action
from .models import VerificationAttempt


def certificate_artifacts_are_intact(certificate):
    """Fail closed when a stored certificate artifact lacks or fails its hash."""
    if certificate.file:
        expected = (certificate.file_sha256 or "").strip().lower()
        if not expected:
            return False
        try:
            digest = hashlib.sha256()
            with certificate.file.open("rb") as content:
                for chunk in content.chunks():
                    digest.update(chunk)
            if not hmac.compare_digest(digest.hexdigest(), expected):
                return False
        except (OSError, NotImplementedError, ValueError):
            return False

    try:
        pdf = certificate.pdf_document
    except CertificatePDF.DoesNotExist:
        return True
    expected_pdf = (pdf.sha256 or "").strip().lower()
    if not expected_pdf:
        return False
    actual_pdf = hashlib.sha256(bytes(pdf.content)).hexdigest()
    return hmac.compare_digest(actual_pdf, expected_pdf)


def certificate_verification_state(certificate):
    if certificate is None:
        return "NOT_FOUND", "Certificate was not found in the registry.", False

    status = certificate.status
    if status == Certificate.Status.VERIFIED:
        if not certificate_artifacts_are_intact(certificate):
            return (
                "NOT_VERIFIED",
                "The stored certificate file failed its integrity check and requires issuer review.",
                False,
            )
        return "VERIFIED", "This certificate has been verified against the OneSmarter-CertiVerify registry.", True
    if status == Certificate.Status.PENDING:
        return "PENDING", "This certificate is in the registry but is pending verification.", False
    if status == Certificate.Status.REJECTED:
        return "REJECTED", "This certificate was reviewed and rejected.", False
    if status == Certificate.Status.REVOKED:
        return "REVOKED", "This certificate has been revoked by the issuing authority.", False
    return "NOT_VERIFIED", "This certificate is not currently verified.", False


def record_verification_attempt(certificate, certificate_number, request):
    """Record public lookups consistently, including a status-aware audit event."""
    result, message, is_verified = certificate_verification_state(certificate)
    attempt_result = (
        result if result in VerificationAttempt.Result.values
        else VerificationAttempt.Result.NOT_VERIFIED
    )
    user = request.user if getattr(request.user, "is_authenticated", False) else None
    attempt = VerificationAttempt.objects.create(
        certificate=certificate,
        certificate_number=certificate_number,
        result=attempt_result,
        requested_by=user,
    )
    log_action(
        action=(AuditLog.Action.CERTIFICATE_VERIFIED if is_verified else AuditLog.Action.CERTIFICATE_LOOKUP_FAILED),
        actor=user,
        target_type="Certificate",
        target_id=certificate.pk if certificate else "",
        description=f"Certificate lookup result: {result}",
        metadata={"certificate_number": certificate_number, "result": result, "found": certificate is not None},
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return attempt, result, message, is_verified
