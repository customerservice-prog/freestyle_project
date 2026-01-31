from django.contrib import admin
from .models import Channel, ChannelEntry, FreestyleVideo, ChatMessage, Vote

@admin.register(FreestyleVideo)
class FreestyleVideoAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "duration_seconds", "file", "captions_vtt")
    search_fields = ("title",)

@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("id", "slug", "name", "schedule_epoch")
    search_fields = ("slug", "name")

@admin.register(ChannelEntry)
class ChannelEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "channel", "position", "video")
    list_filter = ("channel",)
    ordering = ("channel", "position")

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "channel", "name", "text", "created")
    list_filter = ("channel",)
    ordering = ("-created",)

@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("id", "channel", "video", "kind", "session_key", "video_start_epoch", "created")
    list_filter = ("channel", "kind")
    ordering = ("-created",)
