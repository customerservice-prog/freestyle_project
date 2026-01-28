import os
from django.http import JsonResponse

# Put any MP4 here for testing (works locally + live)
DEFAULT_DEMO_MP4 = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"

def now_main(request):
    """
    Always returns a valid payload the frontend can play:
    {
      "item": {"video_id": "...", "play_url": "...", "is_hls": false},
      "offset_seconds": 0
    }
    """
    demo_url = os.environ.get("DEMO_MP4_URL", DEFAULT_DEMO_MP4)

    payload = {
        "item": {
            "video_id": "demo",
            "play_url": demo_url,
            "is_hls": False,
        },
        "offset_seconds": 0,
    }
    return JsonResponse(payload)

def captions_for_video(request, video_id: str):
    # Safe default: no captions
    return JsonResponse({"words": []})
