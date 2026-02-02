# freestyle/migrations/0015_autofix_missing_db_schema.py
from django.db import migrations


def _pg_table_exists(schema_editor, table_name: str) -> bool:
    conn = schema_editor.connection
    with conn.cursor() as cursor:
        cursor.execute("SELECT to_regclass(%s);", [table_name])
        return cursor.fetchone()[0] is not None


def autofix(apps, schema_editor):
    conn = schema_editor.connection

    # IMPORTANT: only run this on Postgres
    if conn.vendor != "postgresql":
        return

    # If you later add other tables/columns to repair, put them here.
    # Keep it conservative.
    tables_to_check = [
        "freestyle_freestylevideo",
        "freestyle_channel",
        "freestyle_channelentry",
    ]

    # If a required table is missing (rare), you’d handle it here.
    # For now we just *detect* and do nothing destructive.
    for t in tables_to_check:
        _pg_table_exists(schema_editor, t)


class Migration(migrations.Migration):

    dependencies = [
        ("freestyle", "0014_repair_freestylevideo_columns"),
    ]

    operations = [
        migrations.RunPython(autofix, migrations.RunPython.noop),
    ]
