from django.contrib import admin
from .models import (
    CreatorProfile, FreestyleVideo, Channel, ChannelEntry,
    PlaybackEvent, FreestyleSubmission, ChatMessage, ChatReaction
)

@admin.register(FreestyleVideo)
class FreestyleVideoAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "status", "duration_seconds", "creator", "created_at")
    list_filter = ("status",)
    search_fields = ("title",)


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("id", "slug", "name", "started_at", "created_at")
    search_fields = ("slug", "name")


@admin.register(ChannelEntry)
class ChannelEntryAdmin(admin.ModelAdmin):
    list_display = (
        "id", "channel", "position", "video", "active",
        "has_played_once", "play_count", "added_at"
    )
    list_filter = ("channel", "active", "has_played_once")
    ordering = ("channel", "position", "id")


@admin.register(PlaybackEvent)
class PlaybackEventAdmin(admin.ModelAdmin):
    list_display = ("id", "channel_entry", "event_type", "created_at")
    list_filter = ("event_type",)


@admin.register(FreestyleSubmission)
class FreestyleSubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "email", "status", "created_at")
    list_filter = ("status",)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "channel", "username", "message", "created_at")
    list_filter = ("channel",)
    search_fields = ("username", "message")


@admin.register(ChatReaction)
class ChatReactionAdmin(admin.ModelAdmin):
    list_display = ("id", "channel", "video_id", "client_id", "reaction", "created_at")
    list_filter = ("channel", "reaction")
    search_fields = ("video_id", "client_id")
