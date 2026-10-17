from django.db import migrations, models
import apps.certificates.models


class Migration(migrations.Migration):
    dependencies = [("certificates", "0007_add_template_description_and_layout")]

    operations = [
        migrations.AddField(
            model_name="certificatetemplate",
            name="original_pdf",
            field=models.FileField(blank=True, null=True, upload_to=apps.certificates.models.template_upload_path),
        ),
    ]
