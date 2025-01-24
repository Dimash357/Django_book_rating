import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils.dateparse import parse_date
from django_app.models import Cinematography

class Command(BaseCommand):
    help = 'Fetch and save movies from TMDB'

    def handle(self, *args, **kwargs):
        api_key = settings.TMDB_API_KEY
        url = f'https://api.themoviedb.org/3/movie/popular?api_key={api_key}&language=en-US&page=1'
        response = requests.get(url)
        data = response.json()

        for movie in data['results']:
            Cinematography.objects.update_or_create(
                title=movie['title'],
                defaults={
                    'category': 'movie',
                    'genre': movie['genre_ids'][0] if movie['genre_ids'] else 'none',
                    'description': movie.get('overview', ''),
                    'release_date': parse_date(movie.get('release_date', ''))
                }
            )
        self.stdout.write(self.style.SUCCESS('Successfully fetched and saved movies'))
