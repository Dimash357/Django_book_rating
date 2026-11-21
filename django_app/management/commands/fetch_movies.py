"""Import / refresh titles from TMDB.

    python manage.py fetch_movies                       # all categories, 5 pages each
    python manage.py fetch_movies --categories anime --pages 10

Existing rows are matched by TMDB id first, then by title (rows imported by
older versions of this command), so nothing is duplicated or deleted.
"""
import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_date

from django_app import tmdb
from django_app.genres import ANIMATION_TMDB_ID, GENRES, genre_slugs_from_tmdb
from django_app.models import Cinematography, Genre

SOURCES = {
    'movie': [('movie', '/movie/popular', {}), ('movie', '/movie/top_rated', {})],
    'series': [('tv', '/tv/popular', {}), ('tv', '/tv/top_rated', {})],
    'anime': [
        ('tv', '/discover/tv', {'with_genres': ANIMATION_TMDB_ID, 'with_original_language': 'ja',
                                'sort_by': 'popularity.desc'}),
        ('movie', '/discover/movie', {'with_genres': ANIMATION_TMDB_ID, 'with_original_language': 'ja',
                                      'sort_by': 'popularity.desc'}),
    ],
    'cartoons': [
        ('movie', '/discover/movie', {'with_genres': ANIMATION_TMDB_ID, 'sort_by': 'popularity.desc'}),
        ('tv', '/discover/tv', {'with_genres': ANIMATION_TMDB_ID, 'sort_by': 'popularity.desc'}),
    ],
}


def classify(media, genre_ids, language):
    if ANIMATION_TMDB_ID in (genre_ids or []):
        return 'anime' if language == 'ja' else 'cartoons'
    return 'series' if media == 'tv' else 'movie'


class Command(BaseCommand):
    help = 'Fetch movies, series, cartoons and anime from TMDB and save them to the database'

    def add_arguments(self, parser):
        parser.add_argument('--pages', type=int, default=5, help='Pages per source (20 titles each)')
        parser.add_argument('--categories', nargs='+', choices=list(SOURCES), default=list(SOURCES))

    def handle(self, *args, **options):
        if not tmdb.is_configured():
            raise CommandError('Set the TMDB_API_KEY environment variable first (see README.md).')

        self.genres = {}
        for slug, name in GENRES.items():
            self.genres[slug], _ = Genre.objects.get_or_create(slug=slug, defaults={'name': name})

        created = updated = 0
        for category in options['categories']:
            for media, path, params in SOURCES[category]:
                for page in range(1, options['pages'] + 1):
                    try:
                        data = tmdb.get(path, {**params, 'page': page})
                    except tmdb.TMDBError as exc:
                        self.stderr.write(f'{path} page {page}: {exc}')
                        break
                    for raw in data.get('results', []):
                        was_created = self.save(raw, media)
                        if was_created is None:
                            continue
                        created += was_created
                        updated += not was_created
                    if page >= data.get('total_pages', 0):
                        break
            self.stdout.write(f'{category}: done')
        self.stdout.write(self.style.SUCCESS(f'Created {created}, updated {updated} titles.'))

    @transaction.atomic
    def save(self, raw, media):
        title = raw.get('title') or raw.get('name')
        if not title or not raw.get('id'):
            return None
        genre_ids = raw.get('genre_ids', [])
        slugs = genre_slugs_from_tmdb(genre_ids)
        date = parse_date(raw.get('release_date') or raw.get('first_air_date') or '')
        values = {
            'title': title[:200],
            'original_title': (raw.get('original_title') or raw.get('original_name') or '')[:200],
            'category': classify(media, genre_ids, raw.get('original_language')),
            'genre': ','.join(slugs)[:100],
            'description': raw.get('overview') or '',
            'release_date': date or datetime.date.today(),
            'poster_path': raw.get('poster_path') or '',
            'backdrop_path': raw.get('backdrop_path') or '',
            'tmdb_rating': raw.get('vote_average'),
            'tmdb_vote_count': raw.get('vote_count') or 0,
            'popularity': raw.get('popularity') or 0,
            'original_language': (raw.get('original_language') or '')[:10],
            'media_type': media,
        }
        item = Cinematography.objects.filter(media_type=media, tmdb_id=raw['id']).first()
        if item is None:
            # Legacy rows (imported before tmdb_id existed) are matched by title.
            item = Cinematography.objects.filter(title=values['title'], tmdb_id__isnull=True).first()
        was_created = item is None
        if was_created:
            item = Cinematography(tmdb_id=raw['id'])
        item.tmdb_id = raw['id']
        for field, value in values.items():
            if field == 'description' and not value and item.description:
                continue  # don't wipe an existing description with an empty translation
            setattr(item, field, value)
        item.save()
        item.genres.add(*[self.genres[s] for s in slugs if s in self.genres])
        return was_created
