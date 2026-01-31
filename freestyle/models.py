from django.db import models

class Channel(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=120, default="Main")
    schedule_epoch = models.IntegerField(default=0)

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
    duration_seconds = models.IntegerField(default=0)
    captions_vtt = models.FileField(upload_to="freestyle_captions/", null=True, blank=True)

    def __str__(self):
        return self.title


class ChannelEntry(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    position = models.IntegerField(default=1)
    video = models.ForeignKey(FreestyleVideo, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("channel", "position")

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
