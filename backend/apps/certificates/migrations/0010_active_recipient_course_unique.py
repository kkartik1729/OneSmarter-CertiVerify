from django.db import migrations, models
from django.db.models.functions import Lower, Trim


def prevent_duplicate_active_certificates(apps, schema_editor):
    Certificate = apps.get_model("certificates", "Certificate")
    duplicates = (
        Certificate.objects.filter(status="VERIFIED", course__isnull=False)
        .exclude(recipient_email="")
        .annotate(normalized_email=Lower(Trim("recipient_email")))
        .values("course_id", "normalized_email")
        .annotate(row_count=models.Count("pk"))
        .filter(row_count__gt=1)
    )
    if duplicates.exists():
        raise RuntimeError(
            "Cannot enforce active recipient/course uniqueness because duplicate certificate records exist. "
            "Review and resolve them explicitly before retrying this migration."
        )


class Migration(migrations.Migration):
    dependencies = [("certificates", "0009_certificate_status_revoked")]

    operations = [
        migrations.RunPython(prevent_duplicate_active_certificates, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="certificate",
            constraint=models.UniqueConstraint(
                models.F("course"),
                Lower(Trim("recipient_email")),
                condition=(
                    models.Q(status="VERIFIED")
                    & models.Q(course__isnull=False)
                    & ~models.Q(recipient_email="")
                ),
                name="cert_unique_active_recipient_course",
            ),
        ),
    ]
