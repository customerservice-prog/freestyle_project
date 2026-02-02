# freestyle/migrations/0014_repair_freestylevideo_columns.py
from django.db import migrations


def _table_names(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        return set(schema_editor.connection.introspection.table_names(cursor))


def _column_names(schema_editor, table_name: str):
    with schema_editor.connection.cursor() as cursor:
        desc = schema_editor.connection.introspection.get_table_description(cursor, table_name)
    return {col.name for col in desc}


def forwards(apps, schema_editor):
    table = "freestyle_freestylevideo"
    tables = _table_names(schema_editor)
    if table not in tables:
        # Nothing to do (fresh DB, or app not installed yet)
        return

    cols = _column_names(schema_editor, table)

    # 1) Add uploaded_by_id if missing
    if "uploaded_by_id" not in cols:
        schema_editor.execute(f'ALTER TABLE "{table}" ADD COLUMN "uploaded_by_id" bigint NULL;')

    # 2) Add video_file if missing (store relative path like "freestyle_videos/xyz.mp4")
    if "video_file" not in cols:
        schema_editor.execute(f'ALTER TABLE "{table}" ADD COLUMN "video_file" varchar(255) NULL;')

    # Refresh cols after adding
    cols = _column_names(schema_editor, table)

    # 3) If legacy "file" column exists, copy it into video_file where video_file is empty
    if "file" in cols and "video_file" in cols:
        schema_editor.execute(
            f'''
            UPDATE "{table}"
            SET "video_file" = "file"
            WHERE ("video_file" IS NULL OR "video_file" = '')
              AND "file" IS NOT NULL
              AND "file" <> '';
            '''
        )


def backwards(apps, schema_editor):
    # Intentionally no-op: we don't want to drop columns in reverse
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("freestyle", "0013_alter_channelentry_options_alter_chatmessage_options_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
