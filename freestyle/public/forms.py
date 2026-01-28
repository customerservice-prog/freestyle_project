from django import forms
from freestyle.models import FreestyleSubmission


class PublicSubmissionForm(forms.ModelForm):
    class Meta:
        model = FreestyleSubmission
        fields = ["title", "email", "video_file"]
