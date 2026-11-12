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
from .ai import recommend_ids
from django.core.paginator import Paginator
from django.utils.http import urlencode



def filter_results(request):
    form = FilterForm(request.GET or None)
    results = Cinematography.objects.none()

    if request.GET and form.is_valid():
        cinematography = form.cleaned_data.get("cinematography")
        genre = form.cleaned_data.get("genre")
        interests = form.cleaned_data.get("interests")
        mood = form.cleaned_data.get("mood")

        qs = Cinematography.objects.all().order_by("id")

        if cinematography and cinematography != "none":
            qs = qs.filter(category=cinematography)

        if genre and genre != "none":
            qs = qs.filter(genre__icontains=genre)

        if interests or mood:
            # Ключ поиска, не включающий номер страницы
            filters = request.GET.copy()
            filters.pop("page", None)
            search_key = filters.urlencode()

            cached_key = request.session.get("movie_search_key")
            cached_ids = request.session.get("movie_search_ids")

            if cached_key == search_key and cached_ids is not None:
                ids = cached_ids
            else:
                candidates = list(qs[:150])
                ids = recommend_ids(
                    candidates,
                    interests,
                    mood,
                    limit=150
                )

                request.session["movie_search_key"] = search_key
                request.session["movie_search_ids"] = ids

            if ids:
                movies_by_id = {
                    movie.id: movie
                    for movie in Cinematography.objects.filter(
                        id__in=ids
                    )
                }

                results = [
                    movies_by_id[movie_id]
                    for movie_id in ids
                    if movie_id in movies_by_id
                ]
            else:
                if interests:
                    qs = qs.filter(
                        description__icontains=interests
                    )

                if mood:
                    qs = qs.filter(
                        description__icontains=mood
                    )

                results = qs
        else:
            results = qs

    # Пагинация: 8 фильмов на страницу
    paginator = Paginator(results, 24)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Сохраняем фильтры при переключении страниц
    params = request.GET.copy()
    params.pop("page", None)

    query_string = params.urlencode()

    return render(
        request,
        "django_app/home.html",
        {
            "form": form,
            "results": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
        }
    )



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