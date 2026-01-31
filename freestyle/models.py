from django.db import models
import math
import time


def mp4_duration_seconds(path: str) -> int:
    """
    Read MP4 duration using pure Python (works on Render too).
    Returns ceil(seconds) to avoid cutting off early.
    """
    try:
        from mutagen.mp4 import MP4
        length = MP4(path).info.length  # float seconds
        if not length:
            return 0
        return int(math.ceil(float(length)))
    except Exception:
        return 0


class Channel(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=120, default="Main")
    schedule_epoch = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        if not self.schedule_epoch:
            self.schedule_epoch = int(time.time())
        super().save(*args, **kwargs)

    def __str__(self):
        return self.slug


class FreestyleVideo(models.Model):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="freestyle_videos/")
    duration_seconds = models.PositiveIntegerField(default=0)
    captions_vtt = models.FileField(upload_to="freestyle_captions/", null=True, blank=True)

    def save(self, *args, **kwargs):
        """
        Save first so file.path exists, then auto-fill duration if it's 0.
        """
        super().save(*args, **kwargs)

        if self.file and (self.duration_seconds is None or self.duration_seconds <= 0):
            secs = mp4_duration_seconds(self.file.path)
            if secs > 0:
                # Update without recursion loop
                FreestyleVideo.objects.filter(pk=self.pk).update(duration_seconds=secs)
                self.duration_seconds = secs

    def __str__(self):
        return self.title


class ChannelEntry(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    position = models.PositiveIntegerField(default=1)
    video = models.ForeignKey(FreestyleVideo, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("channel", "position")
        ordering = ["channel", "position"]

    def __str__(self):
        return f"{self.channel.slug} #{self.position} - {self.video.title}"


class ChatMessage(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    name = models.CharField(max_length=32, default="Guest")
    text = models.CharField(max_length=240)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.channel.slug}: {self.name}"


class Vote(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    video = models.ForeignKey(FreestyleVideo, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=64)
    kind = models.CharField(max_length=8)  # fire/nah
    video_start_epoch = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("channel", "video", "session_key", "video_start_epoch")

    def __str__(self):
        return f"{self.channel.slug} {self.kind} {self.session_key}"
