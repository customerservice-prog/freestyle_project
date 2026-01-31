# freestyle/migrations/0009_fix_missing_columns.py
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("freestyle", "0008_alter_channelentry_options_alter_chatmessage_options_and_more"),
    ]

    operations = [
        # Fix: no such column: freestyle_channel.is_active
        migrations.AddField(
            model_name="channel",
            name="is_active",
            field=models.BooleanField(default=True),
        ),

        # Fix: no such column: freestyle_freestylevideo.file
        # We make it nullable so it won't break existing rows.
        migrations.AddField(
            model_name="freestylevideo",
            name="file",
            field=models.FileField(upload_to="videos/", null=True, blank=True),
        ),

        # Fix: non-nullable field text prompt + missing column if referenced
        migrations.AddField(
            model_name="chatmessage",
            name="text",
            field=models.TextField(default="", blank=True),
        ),
    ]
