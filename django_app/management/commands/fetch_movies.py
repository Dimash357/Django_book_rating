import datetime
import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from django_app.models import Cinematography

TMDB_GENRES = {
    28: 'action', 35: 'comedy', 18: 'drama', 14: 'fantasy',
    27: 'horror', 10749: 'romance', 878: 'sci-fi',
}

class Command(BaseCommand):
    help = 'Fetch and save movies from TMDB'

    def handle(self, *args, **kwargs):
        for page in range(1, 6):
            resp = requests.get(
                'https://api.themoviedb.org/3/movie/popular',
                params={'api_key': settings.TMDB_API_KEY, 'language': 'ru-RU', 'page': page},
                timeout=10,
            )
            resp.raise_for_status()
            for m in resp.json()['results']:
                genres = [TMDB_GENRES[g] for g in m.get('genre_ids', []) if g in TMDB_GENRES]
                Cinematography.objects.update_or_create(
                    title=m['title'],
                    defaults={
                        'category': 'movie',
                        'genre': ','.join(genres),
                        'description': m.get('overview', ''),
                        'release_date': parse_date(m.get('release_date') or '') or datetime.date.today(),
                        'poster_path': m.get('poster_path') or '',
                    },
                )
        self.stdout.write(self.style.SUCCESS('Done'))