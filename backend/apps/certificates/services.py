"""
Certificate service layer for claiming unclaimed certificates and linking them
to verified user accounts.
"""
import logging
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


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
            "Skipping certificate claiming: user %s email is not verified.",
            getattr(user, "username", ""),
        )
        return []

    normalized_email = (user.email or "").strip().lower()
    if not normalized_email:
        logger.warning(
            "Skipping certificate claiming: user %s has an empty email.",
            getattr(user, "username", ""),
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
                    "Failed creating notification for claimed cert %s: %s",
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
        logger.info(
            "Successfully claimed %d certificate(s) for user %s (%s)",
            len(claimed_certs),
            user.username,
            normalized_email,
        )

    if conflicts:
        logger.warning(
            "Skipped %d certificate(s) due to concurrent claim conflicts for user %s (%s): %s",
            len(conflicts),
            user.username,
            normalized_email,
            ", ".join(conflicts),
        )

    return claimed_certs
