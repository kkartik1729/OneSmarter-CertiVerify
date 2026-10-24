from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0007_userprofile_google_sub")]

    operations = [
        migrations.AddField(
            model_name="emailverificationtoken",
            name="attempts",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="password_changed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
