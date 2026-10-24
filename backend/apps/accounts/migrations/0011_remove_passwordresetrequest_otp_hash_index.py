from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0010_legacy_email_verification_evidence")]

    operations = [
        migrations.AlterField(
            model_name="passwordresetrequest",
            name="otp_hash",
            field=models.CharField(max_length=64),
        ),
    ]
