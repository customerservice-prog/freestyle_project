# freestyle/models.py
from django.db import models
from django.utils import timezone


class Channel(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    started_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name


class FreestyleVideo(models.Model):
    title = models.CharField(max_length=255)
    video_file = models.FileField(upload_to="freestyle/videos/", blank=True, null=True)
    playback_url = models.URLField(blank=True, default="")
    duration_seconds = models.PositiveIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    @property
    def best_play_url(self) -> str:
        if self.playback_url:
            return self.playback_url
        if self.video_file:
            try:
                return self.video_file.url
            except Exception:
                return ""
        return ""


class ChannelEntry(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="entries")
    video = models.ForeignKey(FreestyleVideo, on_delete=models.SET_NULL, null=True, blank=True)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    has_played_once = models.BooleanField(default=False)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"{self.channel.slug} #{self.position}"


class ChatMessage(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="chat_messages")
    username = models.CharField(max_length=80, default="anon")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    video = models.ForeignKey(FreestyleVideo, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.username}: {self.message[:30]}"


class VideoReaction(models.Model):
    """
    One vote per (video_id, client_id). reaction = 'fire' or 'nah'
    """
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="video_reactions")
    video = models.ForeignKey(FreestyleVideo, on_delete=models.CASCADE, related_name="reactions")
    client_id = models.CharField(max_length=64, db_index=True)
    reaction = models.CharField(max_length=32, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(fields=["video", "client_id"], name="uniq_vote_per_video_client")
        ]

    def __str__(self):
        return f"{self.reaction} v={self.video_id} cid={self.client_id}"
