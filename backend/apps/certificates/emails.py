"""
Email notifications for certificate issuance and distribution.
"""
import logging
from django.conf import settings
from apps.accounts.emails import send_account_email
from apps.certificates.helpers import get_public_frontend_base_url

logger = logging.getLogger(__name__)


def send_certificate_issued_email(certificate) -> tuple[bool, str]:
    """
    Sends certificate issuance email to the certificate owner.
    Returns (success: bool, error_message: str).
    Gracefully catches failures to prevent interrupting generation.
    """
    owner = certificate.owner
    if not owner or not owner.email:
        return False, "Recipient user has no registered email address."

    frontend_base = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
    public_base = get_public_frontend_base_url()
    login_url = f"{frontend_base}/login"
    my_certificates_url = f"{frontend_base}/user/dashboard/certificates"

    if public_base:
        credential_url = f"{public_base}/verify-certificate/{certificate.certificate_number}"
        linkedin_section = (
            f"Public Credential URL (for LinkedIn & sharing):\n"
            f"  {credential_url}\n\n"
            f"You can add this certificate to your LinkedIn profile under:\n"
            f"  Licenses & Certifications → Name: {certificate.title}\n"
            f"  Issuing Organization: OneSmarter, Inc.\n"
            f"  Credential ID: {certificate.certificate_number}\n"
            f"  Credential URL: {credential_url}\n\n"
        )
    else:
        credential_url = f"{frontend_base}/verify-certificate/{certificate.certificate_number}"
        linkedin_section = (
            f"Verification Link (local):\n"
            f"  {credential_url}\n\n"
            f"Note: For LinkedIn 'Licenses & Certifications', a public HTTPS domain\n"
            f"must be configured via PUBLIC_FRONTEND_URL on your server.\n\n"
        )

    recipient_name = certificate.recipient_name or owner.get_full_name() or owner.username
    course_name = certificate.course_name or (certificate.course.name if certificate.course else certificate.title)

    subject = f"OneSmarter CertiVerify — Certificate Issued: {course_name}"
    message = (
        f"Dear {recipient_name},\n\n"
        f"Congratulations! Your certificate of completion for '{course_name}' has been officially issued and registered in OneSmarter CertiVerify.\n\n"
        f"Certificate Details:\n"
        f"  - Title: {certificate.title}\n"
        f"  - Course: {course_name}\n"
        f"  - Certificate Number: {certificate.certificate_number}\n"
        f"  - Issue Date: {certificate.issue_date}\n\n"
        f"{linkedin_section}"
        f"You can log in and view or download your certificate anytime:\n"
        f"  - Sign in: {login_url}\n"
        f"  - My Certificates: {my_certificates_url}\n\n"
        f"Best regards,\n"
        f"OneSmarter, Inc. Verification Team"
    )

    try:
        send_account_email(owner.email, subject, message)
        return True, ""
    except Exception as exc:
        err_msg = str(exc)
        logger.warning(
            "Failed sending certificate email to %s for %s: %s",
            owner.email, certificate.certificate_number, err_msg
        )
        return False, err_msg
