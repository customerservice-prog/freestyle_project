from django.db import models


class Channel(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=120, default="Main")
    schedule_epoch = models.BigIntegerField(default=0)

    def save(self, *args, **kwargs):
        if not self.schedule_epoch:
            import time
            self.schedule_epoch = int(time.time())
        super().save(*args, **kwargs)

    def __str__(self):
        return self.slug


class FreestyleVideo(models.Model):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="freestyle_videos/")
    duration_seconds = models.PositiveIntegerField(default=0)
    captions_vtt = models.FileField(
        upload_to="freestyle_captions/",
        null=True,
        blank=True
    )

    def __str__(self):
        return self.title


class ChannelEntry(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="entries")
    position = models.PositiveIntegerField(default=1)
    video = models.ForeignKey(FreestyleVideo, on_delete=models.CASCADE, related_name="channel_entries")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["channel", "position"], name="uniq_channel_position"),
        ]
        ordering = ["channel_id", "position"]

    def __str__(self):
        return f"{self.channel.slug} #{self.position} - {self.video.title}"


class ChatMessage(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="chat_messages")
    name = models.CharField(max_length=32, default="Guest")
    text = models.CharField(max_length=240)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.channel.slug}: {self.name}"


class Vote(models.Model):
    KIND_FIRE = "fire"
    KIND_NAH = "nah"
    KIND_CHOICES = [(KIND_FIRE, "Fire"), (KIND_NAH, "Nah")]

    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="votes")
    video = models.ForeignKey(FreestyleVideo, on_delete=models.CASCADE, related_name="votes")
    session_key = models.CharField(max_length=64)
    kind = models.CharField(max_length=8, choices=KIND_CHOICES)
    video_start_epoch = models.BigIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["channel", "video", "session_key", "video_start_epoch"],
                name="uniq_vote_per_session_start",
            )
        ]

    def __str__(self):
        return f"{self.channel.slug} {self.kind} {self.session_key}"
