from django.conf import settings
from django.db import models
from django.utils import timezone

# inside FreestyleVideo:
captions_words = models.JSONField(blank=True, null=True, default=list)
captions_model = models.CharField(max_length=50, blank=True, default="")
captions_updated_at = models.DateTimeField(blank=True, null=True)

class CreatorProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="creator_profile",
    )
    display_name = models.CharField(max_length=120, blank=True, default="")
    is_trusted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.display_name or self.user.get_username()


class FreestyleVideo(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("published", "Published"),
        ("rejected", "Rejected"),
    ]

    title = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="published")

    duration_seconds = models.PositiveIntegerField(default=30)

    video_file = models.FileField(upload_to="freestyle_videos/", blank=True, null=True)
    playback_url = models.URLField(blank=True, default="")
    thumbnail_url = models.URLField(blank=True, default="")

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="freestyle_videos",
    )

    # --- Captions ---
    # Stored as list of { "w": "word", "s": 0.123, "e": 0.456 }
    captions_words = models.JSONField(blank=True, null=True, default=list)
    captions_updated_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def get_play_url(self) -> str:
        if self.playback_url:
            return self.playback_url
        if self.video_file:
            try:
                return self.video_file.url
            except Exception:
                return ""
        return ""

    def is_hls(self) -> bool:
        u = (self.get_play_url() or "").lower()
        return u.endswith(".m3u8") or "m3u8" in u

    def __str__(self):
        return f"{self.id}: {self.title}"


class Channel(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.slug


class ChannelEntry(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="entries")
    video = models.ForeignKey(FreestyleVideo, on_delete=models.CASCADE, related_name="channel_entries")

    position = models.PositiveIntegerField(default=0, db_index=True)
    active = models.BooleanField(default=True)

    has_played_once = models.BooleanField(default=False)
    play_count = models.PositiveIntegerField(default=0)

    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["channel", "active", "position"])]

    def __str__(self):
        return f"{self.channel.slug} #{self.position} -> {self.video_id}"


class PlaybackEvent(models.Model):
    channel_entry = models.ForeignKey(ChannelEntry, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=20, default="complete")
    created_at = models.DateTimeField(auto_now_add=True)


class FreestyleSubmission(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    title = models.CharField(max_length=255)
    email = models.EmailField()
    video_file = models.FileField(upload_to="freestyle_submissions/", blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    created_video = models.ForeignKey(
        FreestyleVideo,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="from_submissions",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.id}: {self.title} ({self.status})"
