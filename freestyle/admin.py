from django.contrib import admin
from .models import Channel, FreestyleVideo, ChannelEntry, ChatMessage, VideoReaction

@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("id", "slug", "name", "started_at")
    search_fields = ("slug", "name")

@admin.register(FreestyleVideo)
class FreestyleVideoAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "duration_seconds", "created_at")
    search_fields = ("title",)
    readonly_fields = ("created_at",)

@admin.register(ChannelEntry)
class ChannelEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "channel", "position", "video", "is_active")
    list_filter = ("channel", "is_active")
    ordering = ("channel", "position", "id")

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "channel", "username", "created_at", "video")
    search_fields = ("username", "message")
    list_filter = ("channel",)

@admin.register(VideoReaction)
class VideoReactionAdmin(admin.ModelAdmin):
    list_display = ("id", "channel", "video", "reaction", "client_id", "created_at")
    list_filter = ("channel", "reaction")
    search_fields = ("client_id",)
