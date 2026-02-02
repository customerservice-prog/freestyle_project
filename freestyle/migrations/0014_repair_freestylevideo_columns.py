from django.db import migrations

SQL = """
ALTER TABLE freestyle_freestylevideo
  ADD COLUMN IF NOT EXISTS uploaded_by_id bigint NULL;

ALTER TABLE freestyle_freestylevideo
  ADD COLUMN IF NOT EXISTS video_file varchar(255) NULL;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='freestyle_freestylevideo' AND column_name='file'
  ) THEN
    EXECUTE 'UPDATE freestyle_freestylevideo SET video_file = file WHERE video_file IS NULL';
  END IF;
END $$;
"""

class Migration(migrations.Migration):
    dependencies = [
        ("freestyle", "0013_alter_channelentry_options_alter_chatmessage_options_and_more"),
    ]

    operations = [
        migrations.RunSQL(SQL, reverse_sql=migrations.RunSQL.noop),
    ]
