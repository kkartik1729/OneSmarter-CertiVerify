from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("certificates", "0008_template_original_pdf")]

    operations = [
        migrations.AlterField(
            model_name="certificate",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("VERIFIED", "Verified"),
                    ("REJECTED", "Rejected"),
                    ("REVOKED", "Revoked"),
                ],
                default="PENDING",
                max_length=10,
            ),
        ),
    ]
