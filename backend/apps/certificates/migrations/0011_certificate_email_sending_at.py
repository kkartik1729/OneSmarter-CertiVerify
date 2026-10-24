from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("certificates", "0010_active_recipient_course_unique")]

    operations = [
        migrations.AddField(
            model_name="certificate",
            name="email_sending_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
    ]
