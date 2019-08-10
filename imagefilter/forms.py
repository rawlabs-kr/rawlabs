from django import forms

from imagefilter.models import File, Image


class FileCreateForm(forms.ModelForm):
    class Meta:
        model = File
        fields = ['title', 'original']