from django import forms
from freestyle.models import FreestyleSubmission, FreestyleVideo

class CreatorUploadForm(forms.Form):
    title = forms.CharField(max_length=255)
    duration_seconds = forms.IntegerField(required=False, initial=30)
    video_file = forms.FileField(required=False)
    playback_url = forms.URLField(required=False)

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("video_file") and not (cleaned.get("playback_url") or "").strip():
            raise forms.ValidationError("Upload an MP4 OR paste a playback URL.")
        return cleaned

class SetPasswordForm(forms.Form):
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        c = super().clean()
        if c.get("password1") != c.get("password2"):
            raise forms.ValidationError("Passwords do not match.")
        return c
