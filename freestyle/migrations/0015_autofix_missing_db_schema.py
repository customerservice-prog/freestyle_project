# freestyle/migrations/0015_autofix_missing_db_schema.py
from django.db import migrations


def _is_postgres(schema_editor) -> bool:
    return schema_editor.connection.vendor == "postgresql"


def _table_exists_pg(schema_editor, table_name: str) -> bool:
    # Postgres-only safe check
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass(%s);", [table_name])
        return cursor.fetchone()[0] is not None


def _column_exists_pg(schema_editor, table_name: str, column_name: str) -> bool:
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s
            LIMIT 1;
            """,
            [table_name, column_name],
        )
        return cursor.fetchone() is not None


def autofix(apps, schema_editor):
    """
    This migration exists ONLY to repair production Postgres schema drift
    caused by earlier manual inserts into django_migrations.

    On SQLite (local dev) we do nothing because:
      - SQLite doesn't have to_regclass()
      - Fresh local DB will be created correctly by normal migrations
    """
    if not _is_postgres(schema_editor):
        return

    # 🔧 Add/repair columns that your Django models expect to exist in production.
    # Keep this list minimal and safe.
    table = "freestyle_freestylevideo"

    if not _table_exists_pg(schema_editor, table):
        return

    # Add missing columns Django is selecting
    if not _column_exists_pg(schema_editor, table, "uploaded_by_id"):
        schema_editor.execute(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS uploaded_by_id bigint NULL;')

    if not _column_exists_pg(schema_editor, table, "video_file"):
        schema_editor.execute(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS video_file varchar(255) NULL;')

    # If older column exists, copy into new one (safe)
    if _column_exists_pg(schema_editor, table, "file") and _column_exists_pg(schema_editor, table, "video_file"):
        schema_editor.execute(f'UPDATE "{table}" SET video_file = file WHERE video_file IS NULL;')


class Migration(migrations.Migration):
    dependencies = [
        ("freestyle", "0014_repair_freestylevideo_columns"),
    ]

    operations = [
        migrations.RunPython(autofix, reverse_code=migrations.RunPython.noop),
    ]
