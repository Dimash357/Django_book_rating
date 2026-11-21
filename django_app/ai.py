"""AI recommendations.

Pipeline
1. ``analyse_query`` turns free-text interests/mood into genre & category hints
   and keywords (no network, works in English and Russian).
2. ``rank_locally`` scores *every* title matching the active filters, so the
   candidate pool comes from the whole database, not the first N rows.
3. The best ``AI_MAX_CANDIDATES`` are sent to Gemini, which re-ranks them.
   Only IDs that exist in the candidate pool are accepted — Gemini can never
   introduce a title or ID that is not in the database.
4. Results are cached; when Gemini is not configured, slow or failing, the
   local ranking is returned instead (and Gemini is skipped for a short
   cool-down period so pages stay fast).
"""
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field

import requests
from django.conf import settings
from django.core.cache import cache
from django.db.models import Max

from .genres import CATEGORY_HINTS, MOOD_GENRE_HINTS

logger = logging.getLogger(__name__)

GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
COOLDOWN_KEY = 'ai:gemini:cooldown'
COOLDOWN_SECONDS = 120

STOPWORDS = {
    'the', 'and', 'for', 'with', 'about', 'that', 'this', 'want', 'like', 'something', 'some',
    'movie', 'movies', 'film', 'films', 'show', 'watch', 'into', 'from', 'more', 'very', 'really',
    'and', 'что', 'это', 'как', 'хочу', 'про', 'для', 'или', 'очень', 'нибудь', 'что-нибудь',
    'посмотреть', 'фильм', 'фильмы', 'люблю', 'нравится', 'нравятся', 'мне', 'меня', 'был', 'чтобы',
}

SOURCE_AI = 'ai'
SOURCE_FALLBACK = 'fallback'


@dataclass
class QueryProfile:
    genres: dict = field(default_factory=dict)       # slug -> weight
    categories: set = field(default_factory=set)
    keywords: list = field(default_factory=list)


@dataclass
class Recommendation:
    ids: list
    source: str
    message: str = ''


def _normalise(text):
    return (text or '').lower().replace('ё', 'е')


def _tokens(text):
    return [t for t in re.findall(r'[\w-]+', _normalise(text)) if len(t) >= 3]


def _stem(token):
    # Very small stemmer: good enough to match "космосе"/"космос", "robots"/"robot".
    return token[:6] if len(token) > 6 else token


def analyse_query(interests, mood):
    text = _normalise(f'{interests or ""} {mood or ""}')
    profile = QueryProfile()
    for words, slugs in MOOD_GENRE_HINTS.items():
        if any(w in text for w in words):
            for rank, slug in enumerate(slugs):
                profile.genres[slug] = profile.genres.get(slug, 0) + (2 if rank == 0 else 1)
    for words, category in CATEGORY_HINTS.items():
        if any(w in text for w in words):
            profile.categories.add(category)
    hint_words = {w for words in list(MOOD_GENRE_HINTS) + list(CATEGORY_HINTS) for w in words}
    seen = set()
    for token in _tokens(interests) + _tokens(mood):
        stem = _stem(token)
        if token in STOPWORDS or stem in seen or any(token.startswith(h) for h in hint_words):
            continue
        seen.add(stem)
        profile.keywords.append(stem)
    return profile


def score_catalog(queryset, interests, mood):
    """Score *every* title in ``queryset``.

    Returns ``[(relevance, quality, id), …]`` best-first. ``relevance`` > 0 means
    the title matches the request (genre, keyword or category hints).
    """
    profile = analyse_query(interests, mood)
    rows = queryset.order_by().values_list(
        'id', 'title', 'original_title', 'description', 'category', 'tmdb_rating', 'popularity')
    genre_map = {}
    through = queryset.model.genres.through
    for item_id, slug in through.objects.filter(
            cinematography_id__in=queryset.order_by().values('id')).values_list(
            'cinematography_id', 'genre__slug'):
        genre_map.setdefault(item_id, set()).add(slug)

    scored = []
    for item_id, title, original, description, category, rating, popularity in rows:
        title_l = _normalise(f'{title} {original}')
        desc_l = _normalise(description)
        relevance = 0.0
        for slug, weight in profile.genres.items():
            if slug in genre_map.get(item_id, ()):
                relevance += 2.0 * weight
        for kw in profile.keywords:
            if kw in title_l:
                relevance += 4.0
            if kw in desc_l:
                relevance += 2.0
        if category in profile.categories:
            relevance += 3.0
        quality = (rating or 0) / 10.0 + min(popularity or 0, 500) / 1000.0
        scored.append((relevance, quality, item_id))
    scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
    return scored


def rank_locally(queryset, interests, mood, limit=None):
    """IDs best-first; only matching titles when anything matches at all."""
    scored = score_catalog(queryset, interests, mood)
    matched = [s[2] for s in scored if s[0] > 0]
    ids = matched or [s[2] for s in scored]
    return ids[:limit] if limit else ids


def _catalog_version(queryset):
    model = queryset.model
    agg = model.objects.aggregate(max_id=Max('id'), changed=Max('updated_at'))
    return f"{model.objects.count()}:{agg['max_id']}:{agg['changed']}"


def _cache_key(interests, mood, filters_key, version):
    raw = json.dumps([(interests or '').strip().lower(), (mood or '').strip().lower(),
                      filters_key, version, settings.GEMINI_MODEL])
    return 'ai:rec:' + hashlib.sha256(raw.encode()).hexdigest()


def recommend(queryset, interests, mood, filters_key=''):
    """Return a :class:`Recommendation` for the (already filtered) queryset."""
    key = _cache_key(interests, mood, filters_key, _catalog_version(queryset))
    cached = cache.get(key)
    if cached:
        return Recommendation(**cached)

    scored = score_catalog(queryset, interests, mood)
    if not scored:
        return Recommendation([], SOURCE_FALLBACK, 'No titles match the selected filters.')
    ranked = [s[2] for s in scored if s[0] > 0] or [s[2] for s in scored]

    # Gemini sees the best local matches first, topped up with the best of the rest,
    # so it can also pick titles our keyword heuristics missed.
    candidates = [s[2] for s in scored][:settings.AI_MAX_CANDIDATES]
    ai_ids = ask_gemini(queryset.model, candidates, interests, mood)
    if ai_ids:
        # AI picks first, then the rest of the locally matched pool as "more like this".
        picked = set(ai_ids)
        rest = [i for i in ranked if i not in picked]
        result = Recommendation(ai_ids + rest, SOURCE_AI, f'{len(ai_ids)} picks selected by Gemini AI.')
        cache.set(key, result.__dict__, settings.AI_CACHE_SECONDS)
        return result

    reason = 'Gemini AI is unavailable right now' if settings.GEMINI_API_KEY else 'Gemini AI is not configured'
    result = Recommendation(ranked, SOURCE_FALLBACK, f'{reason} — showing smart matches from the catalogue.')
    cache.set(key, result.__dict__, 300)
    return result


def _build_prompt(model, candidate_ids, interests, mood):
    items = model.objects.filter(id__in=candidate_ids).prefetch_related('genres')
    by_id = {i.id: i for i in items}
    lines = []
    for cid in candidate_ids:
        item = by_id.get(cid)
        if not item:
            continue
        genres = '/'.join(g.slug for g in item.genres.all()) or item.genre or '-'
        rating = f'{item.tmdb_rating:.1f}' if item.tmdb_rating else '-'
        desc = re.sub(r'\s+', ' ', item.description or '')[:160]
        lines.append(f'{item.id}|{item.title}|{item.year or "-"}|{item.category}|{genres}|{rating}|{desc}')
    return '\n'.join(lines), set(by_id)


def ask_gemini(model, candidate_ids, interests, mood, limit=24):
    """Return Gemini's ranked IDs (subset of ``candidate_ids``) or ``[]``."""
    api_key = settings.GEMINI_API_KEY
    if not api_key or not candidate_ids or cache.get(COOLDOWN_KEY):
        return []

    catalog, valid_ids = _build_prompt(model, candidate_ids, interests, mood)
    system = (
        'You are a film, TV and anime recommendation expert. Understand the user\'s interests, '
        'mood and preferences written in natural language (any language). Choose ONLY from the '
        'catalogue provided; never invent titles or IDs. Respond with JSON only: '
        '{"ids": [<catalogue ids, best match first>]}.'
    )
    user = (
        f'Interests: {interests or "not specified"}\n'
        f'Mood: {mood or "not specified"}\n\n'
        f'Catalogue (id|title|year|category|genres|TMDB rating|description):\n{catalog}\n\n'
        f'Pick up to {limit} titles that best fit the interests and mood. '
        'Consider tone, themes, genre and what the user wants to feel.'
    )
    payload = {
        'model': settings.GEMINI_MODEL,
        'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
        'temperature': 0.3,
        'response_format': {'type': 'json_object'},
    }
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

    for attempt in range(2):
        try:
            response = requests.post(GEMINI_URL, headers=headers, json=payload,
                                     timeout=settings.GEMINI_TIMEOUT)
            if response.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                logger.warning('Gemini HTTP %s, retrying once', response.status_code)
                continue
            response.raise_for_status()
            content = response.json()['choices'][0]['message']['content']
            ids = parse_ids(content, valid_ids, limit)
            if ids:
                return ids
            logger.warning('Gemini returned no usable IDs')
            return []
        except requests.Timeout:
            logger.warning('Gemini timeout (attempt %s)', attempt + 1)
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            logger.error('Gemini error: %s', exc)
            break
    cache.set(COOLDOWN_KEY, True, COOLDOWN_SECONDS)
    return []


def parse_ids(content, valid_ids, limit):
    """Extract IDs from Gemini's answer; anything not in ``valid_ids`` is dropped."""
    if not isinstance(content, str):
        return []
    raw = None
    try:
        data = json.loads(content)
        raw = data.get('ids') if isinstance(data, dict) else data
    except ValueError:
        match = re.search(r'\[[\s\S]*?\]', content)
        if match:
            try:
                raw = json.loads(match.group())
            except ValueError:
                raw = None
    if not isinstance(raw, list):
        return []
    result = []
    for value in raw:
        try:
            item_id = int(value)
        except (TypeError, ValueError):
            continue
        if item_id in valid_ids and item_id not in result:
            result.append(item_id)
        if len(result) >= limit:
            break
    return result
