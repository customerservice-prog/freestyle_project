# freestyle/migrations/0013_alter_channelentry_options_alter_chatmessage_options_and_more.py
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("freestyle", "0012_remove_freestylevideo_sponsor_image_url_and_more"),
    ]

    operations = [
        # This migration was missing from the repo but already exists in the DB history.
        # We add it back as a NO-OP so Django's migration graph is consistent.
    ]
