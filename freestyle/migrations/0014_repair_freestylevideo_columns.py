# freestyle/migrations/0014_repair_freestylevideo_columns.py
from django.db import migrations


def repair_freestylevideo_columns(apps, schema_editor):
    table = "freestyle_freestylevideo"

    with schema_editor.connection.cursor() as cursor:
        try:
            cols = schema_editor.connection.introspection.get_table_description(cursor, table)
        except Exception:
            # Table doesn't exist (fresh DB) — nothing to repair
            return

        existing = {c.name for c in cols}
        vendor = schema_editor.connection.vendor

        def safe_exec(sql):
            try:
                schema_editor.execute(sql)
            except Exception:
                # swallow errors so this stays "repair safe"
                pass

        # 1) uploaded_by_id (Django model expects it, DB is missing it in prod)
        if "uploaded_by_id" not in existing:
            if vendor == "postgresql":
                safe_exec(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS uploaded_by_id bigint NULL;')
            else:
                # sqlite / others
                safe_exec(f'ALTER TABLE "{table}" ADD COLUMN uploaded_by_id integer NULL;')

        # Refresh column list after ALTERs
        try:
            cols = schema_editor.connection.introspection.get_table_description(cursor, table)
            existing = {c.name for c in cols}
        except Exception:
            return

        # 2) video_file (Django model expects it, DB is missing it in prod)
        if "video_file" not in existing:
            if vendor == "postgresql":
                safe_exec(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS video_file varchar(255) NULL;')
            else:
                safe_exec(f'ALTER TABLE "{table}" ADD COLUMN video_file varchar(255) NULL;')

        # Refresh again
        try:
            cols = schema_editor.connection.introspection.get_table_description(cursor, table)
            existing = {c.name for c in cols}
        except Exception:
            return

        # 3) If an older column exists (like "file"), copy it into video_file
        if "file" in existing and "video_file" in existing:
            safe_exec(f'UPDATE "{table}" SET video_file = file WHERE video_file IS NULL;')


class Migration(migrations.Migration):
    dependencies = [
        ("freestyle", "0013_alter_channelentry_options_alter_chatmessage_options_and_more"),
    ]

    operations = [
        migrations.RunPython(repair_freestylevideo_columns, reverse_code=migrations.RunPython.noop),
    ]
