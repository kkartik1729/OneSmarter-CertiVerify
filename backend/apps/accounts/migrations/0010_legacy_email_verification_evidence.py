from django.db import migrations
from django.db.models import Q


def correct_legacy_verification_flags(apps, schema_editor):
    UserProfile = apps.get_model("accounts", "UserProfile")
    Certificate = apps.get_model("certificates", "Certificate")

    evidenced_owner_ids = Certificate.objects.filter(
        status="VERIFIED",
        owner_id__isnull=False,
    ).values_list("owner_id", flat=True).distinct()

    # Migration 0006 set every profile to verified without proof. Preserve the
    # accounts with independent Google verification or an issued credential;
    # the remaining accounts must complete the normal email OTP flow again.
    (
        UserProfile.objects.filter(email_verified=True)
        .filter(Q(google_sub="") | Q(google_sub__isnull=True))
        .exclude(user_id__in=evidenced_owner_ids)
        .update(email_verified=False, email_verified_at=None)
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0009_identity_uniqueness"),
        ("certificates", "0011_certificate_email_sending_at"),
    ]

    operations = [
        migrations.RunPython(correct_legacy_verification_flags, migrations.RunPython.noop),
    ]
