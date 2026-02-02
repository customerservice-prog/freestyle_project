import re
import subprocess
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()


class Channel(models.Model):
    slug = models.SlugField(unique=True, default="main")
    name = models.CharField(max_length=120, default="Main")
    is_default = models.BooleanField(default=False)

    # THIS is the global station “clock” anchor.
    # All viewers share this, so refresh doesn’t restart.
    schedule_started_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name


class SponsorAd(models.Model):
    is_active = models.BooleanField(default=True)
    title = models.CharField(max_length=140, blank=True, default="")
    description = models.TextField(blank=True, default="")
    image_url = models.URLField(blank=True, default="")
    click_url = models.URLField(blank=True, default="")

    def __str__(self):
        return self.title or "Sponsor Ad"


class FreestyleVideo(models.Model):
    uploaded_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="freestyle_videos"
    )

    title = models.CharField(max_length=255)

    # Upload field
    video_file = models.FileField(upload_to="videos/", blank=True, null=True)

    # What the player uses
    play_url = models.CharField(max_length=500, blank=True, default="")

    artwork_url = models.URLField(blank=True, default="")
    duration_seconds = models.PositiveIntegerField(default=0)
    is_hls = models.BooleanField(default=False)

    def __str__(self):
        return self.title

    def _auto_duration_from_file(self, abs_path: str) -> int:
        """
        Uses imageio-ffmpeg’s bundled ffmpeg (no system ffprobe needed).
        Parses Duration: HH:MM:SS.xx from ffmpeg output.
        """
        try:
            from imageio_ffmpeg import get_ffmpeg_exe
            ffmpeg = get_ffmpeg_exe()
        except Exception:
            return 0

        try:
            p = subprocess.run([ffmpeg, "-i", abs_path], capture_output=True, text=True)
            text = (p.stderr or "") + "\n" + (p.stdout or "")
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", text)
            if not m:
                return 0
            hh, mm, ss, _ff = m.groups()
            return int(hh) * 3600 + int(mm) * 60 + int(ss)
        except Exception:
            return 0

    def save(self, *args, **kwargs):
        # If a file is uploaded, force play_url to /media/...
        if self.video_file and not self.is_hls:
            self.play_url = f"{settings.MEDIA_URL}{self.video_file.name}"

        # Auto duration once (MP4 only)
        if self.video_file and not self.is_hls and (self.duration_seconds or 0) == 0:
            try:
                dur = self._auto_duration_from_file(self.video_file.path)
                if dur > 0:
                    self.duration_seconds = dur
            except Exception:
                pass

        super().save(*args, **kwargs)


class ChannelEntry(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="entries")
    video = models.ForeignKey(FreestyleVideo, on_delete=models.CASCADE, related_name="channel_entries")

    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    # True only for real live streams (.m3u8). MP4 rotation should be False.
    is_live = models.BooleanField(default=False)
    started_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.channel.slug}: {self.video.title}"


class ChatMessage(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="chat_messages")
    username = models.CharField(max_length=60)
    message = models.CharField(max_length=280)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.username}: {self.message[:40]}"


class Presence(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="presences")
    sid = models.CharField(max_length=120, db_index=True)
    last_seen = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        unique_together = [("channel", "sid")]

    def __str__(self):
        return f"{self.channel.slug}:{self.sid}"


class VideoReaction(models.Model):
    REACTION_CHOICES = [("fire", "Fire"), ("nah", "Nah")]

    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="reactions")
    video = models.ForeignKey(FreestyleVideo, on_delete=models.CASCADE, related_name="reactions")
    client_id = models.CharField(max_length=120)
    reaction = models.CharField(max_length=10, choices=REACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("channel", "video", "client_id")]

    def __str__(self):
        return f"{self.video_id} {self.client_id} {self.reaction}"
