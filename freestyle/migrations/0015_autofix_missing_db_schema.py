from django.db import migrations


def _table_exists(schema_editor, table_name: str) -> bool:
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass(%s);", [table_name])
        return cursor.fetchone()[0] is not None


def _get_columns(schema_editor, table_name: str) -> set[str]:
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s
            """,
            [table_name],
        )
        return {row[0] for row in cursor.fetchall()}


def autofix(apps, schema_editor):
    # Use historical models from the migration state (apps)
    app_config = apps.get_app_config("freestyle")

    for model in app_config.get_models():
        table = model._meta.db_table

        # If table is missing entirely, create it
        if not _table_exists(schema_editor, table):
            schema_editor.create_model(model)
            continue

        existing_cols = _get_columns(schema_editor, table)

        # Add any missing concrete columns that Django expects
        for field in model._meta.local_fields:
            # Skip implicit/virtual fields
            if getattr(field, "many_to_many", False):
                continue

            col = field.column
            if col not in existing_cols:
                schema_editor.add_field(model, field)


class Migration(migrations.Migration):
    dependencies = [
        ("freestyle", "0014_repair_freestylevideo_columns"),
    ]

    operations = [
        migrations.RunPython(autofix, reverse_code=migrations.RunPython.noop),
    ]
