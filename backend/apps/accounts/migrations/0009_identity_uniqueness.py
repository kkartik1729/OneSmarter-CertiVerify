from django.conf import settings
from django.db import migrations, models


EMAIL_INDEX_NAME = "accounts_auth_user_email_normalized_uniq_idx"


def check_identity_duplicates(apps, schema_editor):
    connection = schema_editor.connection
    UserProfile = apps.get_model("accounts", "UserProfile")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    quote = connection.ops.quote_name

    if connection.vendor == "postgresql":
        table = quote(User._meta.db_table)
        email_column = quote(User._meta.get_field("email").column)
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT 1 FROM {table} WHERE {email_column} <> '' "
                f"GROUP BY LOWER(BTRIM({email_column})) HAVING COUNT(*) > 1 LIMIT 1"
            )
            if cursor.fetchone():
                raise RuntimeError(
                    "Cannot add normalized email uniqueness: duplicate emails exist. "
                    "Review and resolve them explicitly before retrying this migration."
                )

    duplicate_google_sub = (
        UserProfile.objects.exclude(google_sub="")
        .values("google_sub")
        .annotate(count=models.Count("pk"))
        .filter(count__gt=1)
        .exists()
    )
    if duplicate_google_sub:
        raise RuntimeError(
            "Cannot add Google subject uniqueness: duplicate identifiers exist. "
            "Review and resolve them explicitly before retrying this migration."
        )


def create_normalized_email_index(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    quote = connection.ops.quote_name
    table = quote(User._meta.db_table)
    email_column = quote(User._meta.get_field("email").column)
    with connection.cursor() as cursor:
        cursor.execute(
            f"CREATE UNIQUE INDEX {quote(EMAIL_INDEX_NAME)} "
            f"ON {table} (LOWER(BTRIM({email_column}))) "
            f"WHERE {email_column} <> ''"
        )


def drop_normalized_email_index(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"DROP INDEX IF EXISTS {schema_editor.connection.ops.quote_name(EMAIL_INDEX_NAME)}")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0008_emailverification_attempts")]

    operations = [
        migrations.RunPython(check_identity_duplicates, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="userprofile",
            constraint=models.UniqueConstraint(
                fields=("google_sub",),
                condition=~models.Q(google_sub=""),
                name="accounts_unique_google_sub_nonempty",
            ),
        ),
        migrations.RunPython(create_normalized_email_index, drop_normalized_email_index),
    ]
