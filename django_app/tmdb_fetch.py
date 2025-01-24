# tmdb_fetch.py
import requests
from .models import Cinematography

def fetch_and_save_movies(api_key):
    url = f"https://api.themoviedb.org/3/movie/popular?api_key={api_key}&language=ru-RU&page=1"
    response = requests.get(url)
    data = response.json()

    for movie in data['results']:
        Cinematography.objects.update_or_create(
            title=movie['title'],
            defaults={
                'category': 'movie',
                'description': movie['overview'],
                'release_date': movie['release_date'],
                'poster_path': movie['poster_path']
            }
        )
