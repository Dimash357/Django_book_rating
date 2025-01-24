import requests
import os
import django
from django.utils import timezone

# Установить настройки Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_settings.settings")
django.setup()

from django_app.models import Cinematography

API_KEY = '412e1fa867ae38b44964ee52762a6463'
URL = f'https://api.themoviedb.org/3/movie/popular?api_key={API_KEY}&language=ru-RU&page='

def fetch_movies(page):
    response = requests.get(URL + str(page))
    if response.status_code == 200:
        return response.json().get('results', [])
    return []

def save_movies(movies):
    for movie in movies:
        title = movie['title']
        description = movie['overview']
        release_date = movie['release_date'] if movie['release_date'] else timezone.now().date()
        genre = 'none'  # По умолчанию. Можно изменить логику, чтобы соответствовало вашему полю genre
        category = 'movie'

        # Сохранение в базу данных
        Cinematography.objects.update_or_create(
            title=title,
            defaults={
                'description': description,
                'release_date': release_date,
                'genre': genre,
                'category': category
            }
        )

def main():
    for page in range(1, 6):  # Пример: загрузка первых 5 страниц
        movies = fetch_movies(page)
        if not movies:
            break
        save_movies(movies)
        print(f'Page {page} done.')

if __name__ == '__main__':
    main()
