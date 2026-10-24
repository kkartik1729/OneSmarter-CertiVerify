from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("verification", "0002_alter_verificationattempt_result")]

    operations = [
        migrations.AlterField(
            model_name="verificationattempt",
            name="result",
            field=models.CharField(
                choices=[
                    ("FOUND", "Found"),
                    ("VERIFIED", "Verified"),
                    ("PENDING", "Pending"),
                    ("REJECTED", "Rejected"),
                    ("REVOKED", "Revoked"),
                    ("NOT_FOUND", "Not Found"),
                    ("NOT_VERIFIED", "Not Verified"),
                ],
                db_index=True,
                max_length=20,
            ),
        ),
    ]
