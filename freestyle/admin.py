from django.contrib import admin
from .models import Channel, SponsorAd, FreestyleVideo, ChannelEntry, ChatMessage, Presence, VideoReaction


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("id", "slug", "name", "is_default", "schedule_started_at")
    list_editable = ("is_default",)
    search_fields = ("slug", "name")


@admin.register(FreestyleVideo)
class FreestyleVideoAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "is_hls", "duration_seconds", "play_url")
    list_filter = ("is_hls",)
    search_fields = ("title", "play_url")


@admin.register(ChannelEntry)
class ChannelEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "channel", "video", "sort_order", "is_active", "is_live", "started_at")
    list_editable = ("sort_order", "is_active", "is_live")
    list_filter = ("channel", "is_active", "is_live")
    ordering = ("channel", "sort_order", "id")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "channel", "username", "created_at")
    list_filter = ("channel",)
    search_fields = ("username", "message")


@admin.register(Presence)
class PresenceAdmin(admin.ModelAdmin):
    list_display = ("id", "channel", "sid", "last_seen")
    list_filter = ("channel",)
    search_fields = ("sid",)


@admin.register(VideoReaction)
class VideoReactionAdmin(admin.ModelAdmin):
    list_display = ("id", "channel", "video", "client_id", "reaction", "created_at")
    list_filter = ("channel", "reaction")
    search_fields = ("client_id",)


@admin.register(SponsorAd)
class SponsorAdAdmin(admin.ModelAdmin):
    list_display = ("id", "is_active", "title")
    list_editable = ("is_active",)
    search_fields = ("title",)
