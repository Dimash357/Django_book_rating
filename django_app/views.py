from django.contrib.auth import logout, authenticate, login
from django.http import HttpRequest, HttpResponse
from .models import Cinematography
from .forms import FilterForm
from django_app import models
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import authenticate, login as auth_login
from django.db import IntegrityError

from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.urls import reverse
from .forms import ProfileUpdateForm


def filter_results(request):
    form = FilterForm(request.GET or None)
    results = Cinematography.objects.none()  # Изначально пустой QuerySet

    if request.GET:
        if form.is_valid():
            cinematography = form.cleaned_data.get('cinematography')
            genre = form.cleaned_data.get('genre')
            interests = form.cleaned_data.get('interests')
            mood = form.cleaned_data.get('mood')

            results = Cinematography.objects.all()

            if cinematography and cinematography != 'none':
                results = results.filter(category=cinematography)
            if genre and genre != 'none':
                results = results.filter(genre=genre)
            if interests:
                results = results.filter(description__icontains=interests)
            if mood:
                results = results.filter(description__icontains=mood)

            # Debug messages
            print(f"Cinematography: {cinematography}")
            print(f"Genre: {genre}")
            print(f"Interests: {interests}")
            print(f"Mood: {mood}")
            print(f"Results count: {results.count()}")
        else:
            print("Form is not valid")
            print(f"Form errors: {form.errors}")

    else:
        print("hello")
    return render(request, 'django_app/home.html', {'form': form, 'results': results})


def all_movies(request):
    movies = Cinematography.objects.filter(category='movie')
    return render(request, 'django_app/all_movies.html', {'movies': movies})


def register(request):
    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        email = request.POST.get("email", "")

        # Проверка, существует ли email
        if User.objects.filter(email=email).exists():
            return render(request, 'django_app/register.html', {'error': 'This email is already taken'})

        try:
            user = User.objects.create_user(username=username, password=password, email=email)
            user.save()
            return redirect(reverse('django_app:login'))
        except IntegrityError:
            return render(request, 'django_app/register.html', {'error': 'The username already exists'})
    return render(request, 'django_app/register.html')


def login_(request):
    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect(reverse('django_app:home'))
        else:
            return render(request, 'django_app/login.html', {'error1': 'Login or password is incorrect'})

    return render(request, 'django_app/login.html')


def logout_f(request):
    logout(request)
    return redirect(reverse('django_app:login', args=()))


def profile(request):
    return render(request, 'django_app/profile.html')


# @logging
def profile_update(request):
    if request.method == 'POST':
        pform = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)
        if pform.is_valid:
            pform.save()
            return render(request, 'django_app/profile.html')
    else:
        pform = ProfileUpdateForm(instance=request.user.profile)
    return render(request, 'django_app/profile_update.html', {'pform': pform})


def about(request):
    return render(request, 'django_app/about.html')