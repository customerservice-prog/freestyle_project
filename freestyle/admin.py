from django.contrib import admin
from .models import (
    CreatorProfile,
    FreestyleVideo,
    Channel,
    ChannelEntry,
    PlaybackEvent,
    FreestyleSubmission,
)


@admin.register(CreatorProfile)
class CreatorProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "display_name", "is_trusted", "created_at")
    search_fields = ("user__username", "user__email", "display_name")
    list_filter = ("is_trusted", "created_at")


@admin.register(FreestyleVideo)
class FreestyleVideoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "status",
        "duration_seconds",
        "creator",
        "captions_updated_at",
        "created_at",
    )
    search_fields = ("title",)
    list_filter = ("status", "created_at")
    readonly_fields = ("created_at", "captions_updated_at")


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "created_at")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ChannelEntry)
class ChannelEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "channel", "video", "position", "active", "has_played_once", "play_count", "added_at")
    list_filter = ("channel", "active", "has_played_once")
    ordering = ("channel", "position", "id")


@admin.register(PlaybackEvent)
class PlaybackEventAdmin(admin.ModelAdmin):
    list_display = ("id", "channel_entry", "event_type", "created_at")
    list_filter = ("event_type", "created_at")


@admin.register(FreestyleSubmission)
class FreestyleSubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "email", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("title", "email")
