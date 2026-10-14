"""
Email notifications for certificate issuance and distribution with PDF attachment.
"""
import io
import logging
from django.conf import settings
from django.contrib.auth import get_user_model
from PIL import Image

from apps.accounts.emails import send_account_email
from apps.certificates.helpers import get_public_frontend_base_url
from apps.certificates.models import CertificatePDF

logger = logging.getLogger(__name__)
User = get_user_model()


def _format_date(d) -> str:
    """Format date as DD/MM/YYYY."""
    if not d:
        return "N/A"
    if hasattr(d, "strftime"):
        return d.strftime("%d/%m/%Y")
    s = str(d).strip()
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        parts = s.split("-")
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return s


def _get_or_create_certificate_pdf_bytes(certificate) -> bytes:
    """
    Retrieves the personalized certificate PDF from PostgreSQL CertificatePDF,
    or generates it from the certificate file/template.
    """
    # 1. Try PostgreSQL stored CertificatePDF
    try:
        if hasattr(certificate, "pdf_document") and certificate.pdf_document is not None:
            raw = certificate.pdf_document.content
            if raw:
                # Handle bytes / memoryview
                return bytes(raw)
    except Exception as e:
        logger.warning("Could not read pdf_document for cert %s: %s", certificate.certificate_number, e)

    # 2. Try converting stored certificate.file (e.g. generated PNG) to PDF
    if certificate.file:
        try:
            certificate.file.open("rb")
            img = Image.open(certificate.file).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="PDF", resolution=150)
            pdf_bytes = buf.getvalue()
            # Store in CertificatePDF for future downloads & caching
            try:
                CertificatePDF.store(
                    certificate=certificate,
                    raw_bytes=pdf_bytes,
                    filename=f"{certificate.certificate_number}.pdf",
                )
            except Exception as store_err:
                logger.warning("Failed caching generated PDF in CertificatePDF: %s", store_err)
            return pdf_bytes
        except Exception as file_err:
            logger.warning("Failed converting certificate image file to PDF for %s: %s", certificate.certificate_number, file_err)

    # 3. If neither is available, attempt on-demand rendering using template
    if certificate.template and certificate.template.image:
        try:
            from apps.certificates.generator import generate_certificate_image
            pdf_bytes, _ = generate_certificate_image(
                template_path=certificate.template.image.path,
                student_name=certificate.recipient_name,
                course_name=certificate.course_name or (certificate.course.name if certificate.course else certificate.title),
                start_date=certificate.start_date.strftime("%d/%m/%Y") if certificate.start_date else "",
                end_date=certificate.end_date.strftime("%d/%m/%Y") if certificate.end_date else "",
                issue_date=certificate.issue_date.strftime("%d/%m/%Y") if certificate.issue_date else "",
                certificate_number=certificate.certificate_number,
                issuer_name=certificate.issuer,
                completion_description=certificate.completion_description,
                output_format="PDF",
            )
            CertificatePDF.store(
                certificate=certificate,
                raw_bytes=pdf_bytes,
                filename=f"{certificate.certificate_number}.pdf",
            )
            return pdf_bytes
        except Exception as gen_err:
            logger.error("Failed on-demand rendering of certificate PDF for %s: %s", certificate.certificate_number, gen_err)

    raise ValueError(f"No certificate image or PDF content found for {certificate.certificate_number}.")


def send_certificate_issued_email(certificate) -> tuple[bool, str]:
    """
    Sends certificate issuance email to the recipient with the actual personalized PDF attached.
    Supports both registered and unregistered email recipients.
    Returns (success: bool, error_message: str).
    Gracefully catches failures to prevent crashing generation batches.
    """
    owner = certificate.owner
    recipient_email = ""
    if owner and getattr(owner, "email", None):
        recipient_email = owner.email.strip().lower()
    elif certificate.recipient_email:
        recipient_email = certificate.recipient_email.strip().lower()

    if not recipient_email or "@" not in recipient_email:
        return False, "Recipient has no valid email address."

    # Check whether an account exists for this recipient email
    has_account = (owner is not None) or User.objects.filter(email__iexact=recipient_email).exists()

    frontend_base = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
    public_base = get_public_frontend_base_url()
    login_url = f"{frontend_base}/login"
    register_url = f"{frontend_base}/register"
    my_certificates_url = f"{frontend_base}/user/dashboard/certificates"

    if public_base:
        verification_url = f"{public_base}/verify-certificate/{certificate.certificate_number}"
    else:
        verification_url = f"{frontend_base}/verify-certificate/{certificate.certificate_number}"

    recipient_name = certificate.recipient_name or (owner.get_full_name() if owner else "") or (owner.username if owner else "Student")
    course_name = certificate.course_name or (certificate.course.name if certificate.course else certificate.title)
    start_disp = _format_date(certificate.start_date)
    end_disp = _format_date(certificate.end_date)
    issue_disp = _format_date(certificate.issue_date)

    subject = f"Your OneSmarter Certificate of Completion — {certificate.certificate_number}"

    # Build account instructions depending on account status
    if has_account:
        account_section = (
            "If you already have a OneSmarter CertiVerify account, you can sign in and view or download your certificate from My Certificates:\n"
            f"  - Sign in: {login_url}\n"
            f"  - My Certificates: {my_certificates_url}\n\n"
        )
        account_html = f"""
          <p style="margin: 0 0 10px 0; font-size: 14px; color: #334155;">
            You can sign in and view or download your certificate from My Certificates:
          </p>
          <p style="margin: 0 0 16px 0; font-size: 14px;">
            <a href="{login_url}" style="color: #0d9488; font-weight: 600; text-decoration: underline; margin-right: 16px;">Sign In</a>
            <a href="{my_certificates_url}" style="color: #0d9488; font-weight: 600; text-decoration: underline;">My Certificates</a>
          </p>
        """
    else:
        account_section = (
            "If you already have a OneSmarter CertiVerify account, you can sign in and view or download your certificate from My Certificates.\n\n"
            f"If you do not have an account yet, you can register using the same email address that received this certificate ({recipient_email}). "
            "After verifying your email and registering, your certificate will be available in your account:\n"
            f"  - Register: {register_url}\n\n"
        )
        account_html = f"""
          <p style="margin: 0 0 10px 0; font-size: 14px; color: #334155;">
            If you already have a OneSmarter CertiVerify account, you can sign in and view or download your certificate from My Certificates.
          </p>
          <p style="margin: 0 0 10px 0; font-size: 14px; color: #334155;">
            If you do not have an account yet, you can register using the same email address that received this certificate (<strong>{recipient_email}</strong>). After verifying your email and registering, your certificate will automatically be available in your account:
          </p>
          <p style="margin: 0 0 16px 0; font-size: 14px;">
            <a href="{register_url}" style="color: #0d9488; font-weight: 600; text-decoration: underline;">Create Account & Claim Certificate</a>
          </p>
        """

    message = (
        f"Dear {recipient_name},\n\n"
        f"Congratulations! Your certificate of completion for '{course_name}' has been officially issued and registered in OneSmarter CertiVerify.\n\n"
        "Certificate Details:\n"
        f"- Title: {certificate.title}\n"
        f"- Course: {course_name}\n"
        f"- Certificate Number: {certificate.certificate_number}\n"
        f"- Course Start Date: {start_disp}\n"
        f"- Course End Date: {end_disp}\n"
        f"- Issue Date: {issue_disp}\n\n"
        "Your personalized certificate PDF is attached to this email.\n\n"
        "Certificate Verification:\n"
        f"{verification_url}\n\n"
        f"{account_section}"
        "Best regards,\n\n"
        "OneSmarter, Inc. Verification Team"
    )

    html_message = f"""
      <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #0f172a; line-height: 1.6; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #0f172a; margin-top: 0;">Congratulations, {recipient_name}!</h2>
        <p style="font-size: 15px; color: #334155;">
          Your certificate of completion for <strong>'{course_name}'</strong> has been officially issued and registered in OneSmarter CertiVerify.
        </p>

        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px 20px; margin: 20px 0;">
          <h3 style="margin-top: 0; margin-bottom: 12px; font-size: 15px; color: #0d9488; border-bottom: 1px solid #cbd5e1; padding-bottom: 6px;">
            Certificate Details
          </h3>
          <table style="width: 100%; font-size: 14px; border-collapse: collapse;">
            <tr><td style="padding: 4px 0; color: #64748b; width: 140px;">Title:</td><td style="font-weight: 600;">{certificate.title}</td></tr>
            <tr><td style="padding: 4px 0; color: #64748b;">Course:</td><td style="font-weight: 600;">{course_name}</td></tr>
            <tr><td style="padding: 4px 0; color: #64748b;">Certificate ID:</td><td style="font-family: monospace; font-weight: 700; color: #0d9488;">{certificate.certificate_number}</td></tr>
            <tr><td style="padding: 4px 0; color: #64748b;">Start Date:</td><td>{start_disp}</td></tr>
            <tr><td style="padding: 4px 0; color: #64748b;">End Date:</td><td>{end_disp}</td></tr>
            <tr><td style="padding: 4px 0; color: #64748b;">Issue Date:</td><td>{issue_disp}</td></tr>
          </table>
        </div>

        <div style="background-color: #f0fdfa; border: 1px solid #ccfbf1; border-radius: 8px; padding: 12px 16px; margin: 18px 0; font-size: 14px; color: #0f766e;">
          &#128206; <strong>Your personalized certificate PDF is attached to this email.</strong>
        </div>

        <div style="margin: 24px 0;">
          <h4 style="margin: 0 0 8px 0; font-size: 14px; color: #0f172a;">Certificate Verification:</h4>
          <p style="margin: 0 0 16px 0; font-size: 14px;">
            Anyone can verify the authenticity of this credential directly at:<br/>
            <a href="{verification_url}" style="color: #0d9488; font-weight: 600; text-decoration: underline; word-break: break-all;">{verification_url}</a>
          </p>
        </div>

        {account_html}

        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;" />
        <p style="font-size: 13px; color: #64748b; margin-bottom: 0;">
          Best regards,<br/>
          <strong>OneSmarter, Inc. Verification Team</strong>
        </p>
      </div>
    """

    # Retrieve or generate the PDF attachment bytes
    try:
        pdf_bytes = _get_or_create_certificate_pdf_bytes(certificate)
    except Exception as exc:
        err_msg = f"Failed to retrieve or generate certificate PDF: {exc}"
        logger.error(err_msg)
        return False, err_msg

    attachment_filename = f"{certificate.certificate_number}.pdf"
    attachments = [(attachment_filename, pdf_bytes, "application/pdf")]

    try:
        send_account_email(
            recipient_email=recipient_email,
            subject=subject,
            message=message,
            html_message=html_message,
            attachments=attachments,
        )
        logger.info(
            "Certificate email with PDF attachment '%s' (%d bytes) sent to %s for %s",
            attachment_filename,
            len(pdf_bytes),
            recipient_email,
            certificate.certificate_number,
        )
        return True, ""
    except Exception as exc:
        err_msg = str(exc)
        logger.warning(
            "Failed sending certificate email to %s for %s: %s",
            recipient_email, certificate.certificate_number, err_msg
        )
        return False, err_msg
