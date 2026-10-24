"""
Certificate service layer for claiming unclaimed certificates and linking them
to verified user accounts.
"""
import logging
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def send_certificate_email_once(certificate, sender=None) -> tuple[bool, str]:
    """Send an eligible certificate email and persist its delivery outcome."""
    from apps.certificates.models import Certificate
    from apps.certificates.emails import send_certificate_issued_email

    if certificate.email_sent:
        return True, "Certificate email was already sent."
    if certificate.status != Certificate.Status.VERIFIED:
        return False, "Certificate is not eligible for issuance email."

    send = sender or send_certificate_issued_email
    try:
        email_sent, email_error = send(certificate)
    except Exception:
        logger.exception(
            "Certificate email delivery raised unexpectedly for %s",
            certificate.certificate_number,
        )
        email_sent, email_error = False, "Email delivery failed. Use the existing retry action to try again."

    if not email_sent:
        # Keep transport details in server logs only; SMTP responses can expose
        # hostnames, policy details, or mailbox configuration to API clients.
        logger.warning(
            "Certificate email delivery failed for %s: %s",
            certificate.certificate_number,
            email_error,
        )
        email_error = "Email delivery failed. An administrator can retry delivery."

    certificate.email_sent = bool(email_sent)
    certificate.email_error = (email_error or "")[:2000]
    try:
        certificate.save(update_fields=["email_sent", "email_error", "updated_at"])
    except Exception:
        logger.exception(
            "Could not persist email status for certificate %s",
            certificate.certificate_number,
        )
        certificate.email_error = (
            "Email was accepted, but its delivery status could not be saved."
            if email_sent
            else "Email delivery failed and its status could not be saved."
        )
    return bool(email_sent), certificate.email_error


def claim_unclaimed_certificates_for_user(user) -> list:
    """
    Safely find and claim all unclaimed certificates matching the verified user's email.

    Guarantees:
    1. Only claims certificates if user is authenticated and user.profile.email_verified is True.
    2. Case-insensitive, whitespace-trimmed email comparison (normalized to lowercase).
    3. Runs inside a transaction with row-level locking (select_for_update) to prevent race conditions.
    4. Idempotent: does not duplicate certificate records or change certificate numbers.
    5. Preserves existing certificate numbers, images, PDF documents, and all other fields.
    6. Creates in-app notifications and records each claim in AuditLog.
    7. Never transfers an already-claimed certificate from one user to another.
    8. Skips certificates that already have a different owner (conflict safety).

    Returns a list of Certificate instances that were newly claimed in this call.
    """
    from apps.certificates.models import Certificate
    from apps.notifications.models import Notification
    from apps.audit.models import AuditLog
    from apps.audit.services import log_action

    if not user or not getattr(user, "is_authenticated", False):
        logger.debug("Skipping certificate claiming: user is not authenticated.")
        return []

    # Only claim after email is verified — security requirement
    profile = getattr(user, "profile", None)
    if not profile or not getattr(profile, "email_verified", False):
        logger.debug(
            "Skipping certificate claiming: account email is not verified.",
        )
        return []

    normalized_email = (user.email or "").strip().lower()
    if not normalized_email:
        logger.warning(
            "Skipping certificate claiming: account email is empty.",
        )
        return []

    claimed_certs = []
    conflicts = []

    from django.db.models.functions import Trim, Lower

    with transaction.atomic():
        # Lock all unclaimed certificates matching this normalized email.
        # select_for_update() prevents concurrent claim requests from racing.
        # Trim(Lower(...)) ensures matching succeeds even if email had leading/trailing spaces.
        unclaimed_qs = Certificate.objects.select_for_update().annotate(
            clean_recipient_email=Trim(Lower("recipient_email"))
        ).filter(
            owner__isnull=True,
            clean_recipient_email=normalized_email,
            status=Certificate.Status.VERIFIED,
        )
        unclaimed = list(unclaimed_qs)

        for cert in unclaimed:
            # Double-check: if another concurrent request claimed it first, skip.
            if cert.owner_id is not None:
                conflicts.append(cert.certificate_number)
                logger.warning(
                    "Certificate %s was claimed by another process concurrently; skipping.",
                    cert.certificate_number,
                )
                continue

            # Assign owner and normalize email in the same atomic save
            cert.owner = user
            cert.recipient_email = normalized_email
            cert.save(update_fields=["owner", "recipient_email", "updated_at"])
            claimed_certs.append(cert)

            # In-app notification
            try:
                Notification.objects.create(
                    recipient=user,
                    notification_type=Notification.NotificationType.CERTIFICATE_CREATED,
                    title=f"Certificate Linked: {cert.course_name or cert.title}",
                    message=(
                        f"Your certificate ({cert.certificate_number}) for "
                        f"{cert.course_name or cert.title} has been linked to your account."
                    ),
                    certificate=cert,
                )
            except Exception as notif_err:
                logger.warning(
                    "Failed creating notification for claimed certificate %s: %s",
                    cert.certificate_number,
                    notif_err,
                )

            # Audit log
            try:
                log_action(
                    action=AuditLog.Action.CERTIFICATE_CLAIMED,
                    actor=user,
                    target_type="Certificate",
                    target_id=cert.id,
                    description=(
                        f"Certificate {cert.certificate_number} claimed by verified user "
                        f"{user.username} ({normalized_email})"
                    ),
                    metadata={
                        "certificate_number": cert.certificate_number,
                        "recipient_email": normalized_email,
                        "user_id": user.id,
                    },
                )
            except Exception as audit_err:
                logger.warning(
                    "Failed creating audit log for claimed cert %s: %s",
                    cert.certificate_number,
                    audit_err,
                )

    if claimed_certs:
        # Issuance already attempted delivery before an unregistered recipient
        # could claim the record. Reuse that same delivery path only for a
        # recorded failure; successful deliveries are never duplicated.
        for cert in claimed_certs:
            if cert.email_sent or not cert.email_error:
                continue
            send_certificate_email_once(cert)

        logger.info(
            "Successfully claimed %d certificate(s) for account id %s",
            len(claimed_certs),
            user.pk,
        )

    if conflicts:
        logger.warning(
            "Skipped %d certificate(s) due to concurrent claim conflicts for account id %s: %s",
            len(conflicts),
            user.pk,
            ", ".join(conflicts),
        )

    return claimed_certs
