from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.forms import ClearableFileInput

from .models import Cinematography, Genre, Rating, Review, UserList, WatchlistEntry, profile

SORT_CHOICES = [
    ('popular', 'Most popular'),
    ('rating', 'TMDB rating'),
    ('user_rating', 'Community rating'),
    ('newest', 'Newest'),
    ('oldest', 'Oldest'),
    ('title', 'Title A–Z'),
]
AI_SORT = ('relevance', 'Best match (AI)')


class CatalogFilterForm(forms.Form):
    q = forms.CharField(max_length=100, required=False, label='Search')
    category = forms.ChoiceField(choices=[('', 'All categories')] + Cinematography.CATEGORY_CHOICES,
                                 required=False)
    genres = forms.MultipleChoiceField(required=False, widget=forms.CheckboxSelectMultiple)
    genre_mode = forms.ChoiceField(choices=[('any', 'Any selected genre'), ('all', 'All selected genres')],
                                   required=False)
    year_from = forms.IntegerField(min_value=1870, max_value=2100, required=False)
    year_to = forms.IntegerField(min_value=1870, max_value=2100, required=False)
    min_rating = forms.FloatField(min_value=0, max_value=10, required=False, label='Min TMDB rating')
    sort = forms.ChoiceField(choices=[AI_SORT] + SORT_CHOICES, required=False)
    interests = forms.CharField(max_length=300, required=False)
    mood = forms.CharField(max_length=150, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['genres'].choices = list(Genre.objects.values_list('slug', 'name'))

    def clean(self):
        data = super().clean()
        y1, y2 = data.get('year_from'), data.get('year_to')
        if y1 and y2 and y1 > y2:
            data['year_from'], data['year_to'] = y2, y1
        return data


class RegisterForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput, min_length=8)

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        User.username_validator(username)
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('The username already exists.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('This email is already taken.')
        return email

    def clean(self):
        data = super().clean()
        if data.get('password') and data.get('username'):
            user = User(username=data['username'], email=data.get('email', ''))
            try:
                validate_password(data['password'], user)
            except forms.ValidationError as exc:
                self.add_error('password', exc)
        return data


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = profile
        fields = ['image', 'description', 'city', 'first', 'second', 'third', 'forth']
        labels = {
            'image': 'Avatar', 'description': 'About me', 'first': 'Gallery photo 1',
            'second': 'Gallery photo 2', 'third': 'Gallery photo 3', 'forth': 'Gallery photo 4',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'city': forms.TextInput(),
            'image': ClearableFileInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('description', 'city', 'first', 'second', 'third', 'forth'):
            self.fields[name].required = False
        for f in self.fields.values():
            f.widget.attrs.setdefault('class', 'form-control')


class RatingForm(forms.ModelForm):
    class Meta:
        model = Rating
        fields = ['score']


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['text', 'contains_spoilers']
        labels = {'text': 'Your review', 'contains_spoilers': 'Contains spoilers'}
        widgets = {'text': forms.Textarea(attrs={'rows': 4, 'class': 'form-control',
                                                 'placeholder': 'What did you think?'})}


class StatusForm(forms.Form):
    status = forms.ChoiceField(choices=[('', 'Remove')] + WatchlistEntry.STATUS_CHOICES, required=False)


class UserListForm(forms.ModelForm):
    class Meta:
        model = UserList
        fields = ['name', 'description', 'is_public']
        labels = {'is_public': 'Visible to other users'}
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Weekend marathon'}),
            'description': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        qs = UserList.objects.filter(user=self.user, name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('You already have a list with this name.')
        return name
