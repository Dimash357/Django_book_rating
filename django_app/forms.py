from django import forms
from .models import Cinematography
from django.forms import ClearableFileInput
from .models import profile


class FilterForm(forms.Form):
    cinematography = forms.ChoiceField(choices=Cinematography.CATEGORY_CHOICES, required=False)
    genre = forms.ChoiceField(choices=Cinematography.GENRE_CHOICES, required=False)
    interests = forms.CharField(max_length=100, required=False)
    mood = forms.CharField(max_length=100, required=False)


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = profile
        fields = ['image', 'description', 'city', 'first', 'second', 'third', 'forth']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'cols': 40}),
            'image': ClearableFileInput(attrs={'class': 'form-control-file'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False
        self.fields['city'].required = False
        self.fields['first'].required = False
        self.fields['second'].required = False
        self.fields['third'].required = False
        self.fields['forth'].required = False