from django import forms
from django.core.exceptions import FieldDoesNotExist

from .models import FreestyleSubmission, FreestyleVideo


def _pick_field(model, candidates):
    """
    Return the first field name that exists on model, else None.
    """
    for name in candidates:
        try:
            model._meta.get_field(name)
            return name
        except FieldDoesNotExist:
            continue
        except Exception:
            continue
    return None


# --- Detect fields on FreestyleSubmission ---
SUB_FILE_FIELD = _pick_field(FreestyleSubmission, ["video_file", "file", "upload", "media_file"])
SUB_DURATION_FIELD = _pick_field(FreestyleSubmission, ["duration_seconds", "duration", "seconds"])
SUB_PLAYBACK_FIELD = _pick_field(FreestyleSubmission, ["playback_url", "url", "play_url", "stream_url"])


class PublicSubmissionForm(forms.ModelForm):
    """
    Public upload form.

    IMPORTANT:
    - Only includes model fields that really exist (prevents FieldError).
    - Adds optional non-model fields if you want them later (but does not break imports).
    """

    # Optional extra inputs (NOT stored on FreestyleSubmission unless your model has those fields)
    playback_url = forms.URLField(required=False, label="Playback URL (optional)")
    duration_seconds = forms.IntegerField(required=False, min_value=1, label="Duration seconds (optional)")

    class Meta:
        model = FreestyleSubmission
        fields = [f for f in ["title", "email"] if _pick_field(FreestyleSubmission, [f])]

        # Add the actual upload field if it exists
        if SUB_FILE_FIELD:
            fields.append(SUB_FILE_FIELD)

        # If your submission model actually has these, include them too
        if SUB_PLAYBACK_FIELD:
            fields.append(SUB_PLAYBACK_FIELD)
        if SUB_DURATION_FIELD:
            fields.append(SUB_DURATION_FIELD)

    def clean_duration_seconds(self):
        v = self.cleaned_data.get("duration_seconds")
        if v is None:
            return v
        try:
            return int(v)
        except Exception:
            return None


# --- Detect fields on FreestyleVideo for creator uploads ---
VID_FILE_FIELD = _pick_field(FreestyleVideo, ["video_file", "file", "video", "upload", "media_file"])
VID_DURATION_FIELD = _pick_field(FreestyleVideo, ["duration_seconds", "duration", "seconds"])
VID_PLAYBACK_FIELD = _pick_field(FreestyleVideo, ["playback_url", "url", "play_url", "stream_url"])


class CreatorUploadForm(forms.ModelForm):
    """
    Creator upload form (staff/creator).
    Uses real FreestyleVideo fields only (auto-detected).
    """
    class Meta:
        model = FreestyleVideo
        fields = [f for f in ["title"] if _pick_field(FreestyleVideo, [f])]

        if VID_FILE_FIELD:
            fields.append(VID_FILE_FIELD)
        if VID_PLAYBACK_FIELD:
            fields.append(VID_PLAYBACK_FIELD)
        if VID_DURATION_FIELD:
            fields.append(VID_DURATION_FIELD)
