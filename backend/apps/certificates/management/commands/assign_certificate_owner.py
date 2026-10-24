from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from apps.certificates.models import Certificate
from apps.audit.models import AuditLog
from apps.audit.services import log_action

User = get_user_model()


class Command(BaseCommand):
    help = "Safely assign or reassign a certificate's owner in PostgreSQL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--certificate",
            type=str,
            required=True,
            help="Certificate ID or unique certificate number (e.g. CERT-2026-002)",
        )
        parser.add_argument(
            "--user",
            type=str,
            required=True,
            help="Target registered user ID, username, or email",
        )

    def handle(self, *args, **options):
        cert_ident = options["certificate"].strip()
        user_ident = options["user"].strip()

        # Find certificate by ID or certificate_number
        if cert_ident.isdigit():
            cert = Certificate.objects.filter(id=int(cert_ident)).first()
        else:
            cert = Certificate.objects.filter(certificate_number__iexact=cert_ident).first()

        if not cert:
            raise CommandError(f"Certificate '{cert_ident}' not found in PostgreSQL.")

        # Find target user by ID, username, or email
        user = None
        if user_ident.isdigit():
            user = User.objects.filter(id=int(user_ident)).first()
        if not user:
            user = User.objects.filter(username__iexact=user_ident).first()
        if not user:
            user = User.objects.filter(email__iexact=user_ident).first()

        if not user:
            raise CommandError(f"Registered user '{user_ident}' not found in PostgreSQL.")

        old_owner = cert.owner
        old_owner_name = old_owner.username if old_owner else "(unassigned)"
        cert.owner = user
        cert.save(update_fields=["owner", "updated_at"])

        log_action(
            action=AuditLog.Action.OTHER,
            actor=None,
            target_type="Certificate",
            target_id=cert.id,
            description=f"Admin CLI reassigned certificate owner from {old_owner_name} to {user.username}",
            metadata={
                "certificate_number": cert.certificate_number,
                "old_owner_id": old_owner.id if old_owner else None,
                "old_owner_username": old_owner_name,
                "new_owner_id": user.id,
                "new_owner_username": user.username,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully reassigned certificate {cert.certificate_number} (ID: {cert.id}) "
                f"from '{old_owner_name}' to '{user.username}' (ID: {user.id})."
            )
        )
