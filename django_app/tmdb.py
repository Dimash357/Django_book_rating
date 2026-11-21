"""Small TMDB API client used by the importer and detail pages."""
import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

API_ROOT = 'https://api.themoviedb.org/3'
DETAIL_CACHE_SECONDS = 60 * 60 * 24


class TMDBError(Exception):
    pass


def is_configured():
    return bool(settings.TMDB_API_KEY)


def _auth(params):
    key = settings.TMDB_API_KEY
    headers = {'Accept': 'application/json'}
    params = dict(params or {})
    if key.startswith('eyJ'):           # v4 "API Read Access Token"
        headers['Authorization'] = f'Bearer {key}'
    else:                               # classic v3 API key
        params['api_key'] = key
    return params, headers


def get(path, params=None, timeout=10):
    if not is_configured():
        raise TMDBError('TMDB_API_KEY is not configured')
    params, headers = _auth(params)
    params.setdefault('language', settings.TMDB_LANGUAGE)
    try:
        response = requests.get(f'{API_ROOT}{path}', params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise TMDBError(str(exc)) from exc


def title_details(item):
    """Extra details (runtime, cast, trailer…) for a catalogue item, cached for a day.

    Returns ``None`` when TMDB is not configured, the item has no TMDB id or the
    request fails — detail pages must work without it.
    """
    if not item.tmdb_id or not is_configured():
        return None
    media = item.tmdb_media_type
    key = f'tmdb:details:{media}:{item.tmdb_id}:{settings.TMDB_LANGUAGE}'
    cached = cache.get(key)
    if cached is not None:
        return cached or None
    try:
        data = get(f'/{media}/{item.tmdb_id}', {'append_to_response': 'credits,videos'})
    except TMDBError as exc:
        logger.warning('TMDB details failed for %s/%s: %s', media, item.tmdb_id, exc)
        cache.set(key, {}, 60 * 10)
        return None
    details = _normalise(data, media)
    cache.set(key, details, DETAIL_CACHE_SECONDS)
    return details


def _normalise(data, media):
    runtime = data.get('runtime')
    if not runtime and data.get('episode_run_time'):
        runtime = data['episode_run_time'][0]
    cast = [
        {
            'name': c.get('name', ''),
            'character': c.get('character', ''),
            'profile_url': f"{settings.TMDB_IMAGE_BASE}w185{c['profile_path']}" if c.get('profile_path') else '',
        }
        for c in (data.get('credits') or {}).get('cast', [])[:12]
    ]
    crew = (data.get('credits') or {}).get('crew', [])
    directors = [c['name'] for c in crew if c.get('job') == 'Director'][:3]
    creators = [c.get('name') for c in data.get('created_by', [])][:3]
    trailer = ''
    for video in (data.get('videos') or {}).get('results', []):
        if video.get('site') == 'YouTube' and video.get('type') in ('Trailer', 'Teaser'):
            trailer = f"https://www.youtube.com/watch?v={video['key']}"
            break
    return {
        'tagline': data.get('tagline') or '',
        'runtime': runtime,
        'status': data.get('status') or '',
        'seasons': data.get('number_of_seasons'),
        'episodes': data.get('number_of_episodes'),
        'countries': [c.get('name') for c in data.get('production_countries', [])][:4]
                     or data.get('origin_country', [])[:4],
        'companies': [c.get('name') for c in data.get('production_companies', [])][:4],
        'languages': [lang.get('english_name') for lang in data.get('spoken_languages', [])][:4],
        'budget': data.get('budget') or 0,
        'revenue': data.get('revenue') or 0,
        'homepage': data.get('homepage') or '',
        'directors': directors or creators,
        'director_label': 'Director' if directors else 'Created by',
        'cast': cast,
        'trailer_url': trailer,
        'vote_average': data.get('vote_average'),
        'vote_count': data.get('vote_count'),
    }
