# Movie rating

A Django platform for discovering **movies, series, cartoons and anime**, getting
**AI recommendations** (Google Gemini) from your mood and interests, and keeping
personal **ratings, reviews, watchlists and lists**. Catalogue data and images come
from [TMDB](https://www.themoviedb.org/).

## Features

- **Catalogue & filters**: separate pages for Movies, Series, Cartoons and Anime;
  search by title (also Cyrillic); several genres per title, matching any or all
  selected genres; year range; minimum TMDB rating; sorting by popularity, TMDB
  rating, community rating, newest, oldest or title. Each active filter shows as a
  chip you can remove, there is a *Clear filters* button, and pagination keeps
  your filters.
- **AI recommendations**: describe your interests and mood in any language. Every
  title that matches your filters is scored locally, and the best candidates go
  to Gemini, which picks and ranks the final list.
  - Gemini can only return IDs from the catalogue. Any other ID is thrown away,
    so it can never invent a title.
  - Results are cached.
  - If Gemini is not configured, fails or times out, the page falls back to local
    smart matching. After a failure Gemini is skipped for 2 minutes so pages stay
    fast.
- **Detail pages**: every card is clickable. A detail page shows:
  - poster and backdrop, description, genres and release date;
  - the **TMDB rating**, the **community rating** (from this site's users) and
    **your own rating**, each shown separately;
  - extra TMDB data when available: runtime, seasons, cast, director, trailer,
    budget and box office;
  - reviews and similar titles.
- **Personal tracking**: mark a title as *Watching*, *Plan to Watch* or *Watched*.
  You can do this from any card without reloading the page, or from the detail
  page. You can also rate titles 1–10, write reviews (with a spoiler flag), and
  create public or private lists. You can edit or remove all of these.
- **Profiles**: tabs for each status, ratings, reviews and lists; stats and
  favourite genres; avatar and photo gallery. Public profiles are at `/u/<username>/`.
- **Security**: secrets come from environment variables; logout and all state
  changes are POST requests with CSRF protection; redirects only go to safe
  `next` URLs; passwords are validated; ownership is checked on every edit.

## Tech stack

Python 3.10+, Django 5.2, SQLite, Bootstrap 5.3 + Bootstrap Icons, vanilla JS,
WhiteNoise, Requests, Pillow, TMDB API, Google Gemini (OpenAI-compatible endpoint).

## Installation

```bash
git clone <repo-url> && cd Django_book_rating
```

```bash
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

```bash
cp .env.example .env     # then edit the values
```

```bash
python manage.py migrate
```

```bash
python manage.py runserver
```

Open http://127.0.0.1:8000/. To use the admin, create an account with
`python manage.py createsuperuser`.

## Environment variables

The settings read a `.env` file in the project root when one is present. Real
environment variables take precedence over it.

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_DEBUG` | `True` | Set `False` in production |
| `DJANGO_SECRET_KEY` | dev-only key | **Required** when debug is off |
| `DJANGO_ALLOWED_HOSTS` | `*` in debug | Comma-separated hosts |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | – | e.g. `https://example.com` |
| `DJANGO_DB_PATH` | `db.sqlite3` | SQLite file location |
| `TMDB_API_KEY` | – | TMDB v3 key or v4 read token |
| `TMDB_LANGUAGE` | `ru-RU` | Language of imported titles/descriptions |
| `GEMINI_API_KEY` | – | Enables Gemini recommendations |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Any Gemini chat model |
| `GEMINI_TIMEOUT` | `20` | Seconds per Gemini request |
| `AI_MAX_CANDIDATES` | `300` | Titles sent to Gemini per request |
| `AI_CACHE_SECONDS` | `3600` | Cache lifetime of AI results |

## Migrations

```bash
python manage.py migrate
```

Migrations `0020`–`0021` only add things; they never delete data:

- They add genres (many-to-many), TMDB metadata fields, ratings, reviews,
  watchlist entries and user lists.
- They link every existing title to the genres stored in the old
  comma-separated `genre` column. That column is kept.
- They create a missing profile for every existing user.

Unique constraints stop duplicates: one rating, one review and one watchlist
status per user and title, and one copy of each TMDB title.

Back up `db.sqlite3` before migrating a production database.

## TMDB configuration

1. Create an account at themoviedb.org, go to *Settings → API*, and copy the API
   key (v3) or the Read Access Token (v4).
2. Put it in `TMDB_API_KEY`.
3. Import or refresh the catalogue. The command is safe to re-run: it updates
   existing rows, including ones from older imports matched by title, and never
   deletes anything.

Import every category, 5 pages per source:

```bash
python manage.py fetch_movies
```

Import only anime and cartoons, 10 pages per source:

```bash
python manage.py fetch_movies --categories anime cartoons --pages 10
```

Animated titles go to *Anime* when their original language is Japanese and to
*Cartoons* otherwise. Detail pages fetch extra data (cast, runtime, trailer) on
demand and cache it for 24 hours. Without a key, pages still work; they just
don't show the extra data.

> The TMDB key that used to be hard-coded in the repository should be considered
> public: regenerate it in your TMDB account and keep the new one in `.env`.

## Gemini configuration

1. Create a key at https://aistudio.google.com/apikey.
2. Set `GEMINI_API_KEY` (and optionally `GEMINI_MODEL`).
3. On the home page or in the catalogue's *AI* fields, enter interests such as
   "space, robots, smart plots" and a mood such as "tired, want something cozy".
   The banner above the results says whether Gemini picked them or the offline
   fallback did.

## Usage

- `/` shows the home page: the AI form plus popular rows for each category.
- `/browse/` and `/browse/<movies|series|cartoons|anime>/` show the catalogue with filters.
- `/title/<id>/` is the detail page, where you can rate, review, set a status and add to lists.
- `/profile/` is your profile; `/u/<username>/` is a public profile.
- `/admin/` is the Django admin for titles, genres, ratings, reviews, watchlists and lists.

## Tests

```bash
python manage.py test django_app
```

The tests cover:

- authentication;
- category, genre, combined and search filters, and sorting;
- pagination;
- AI query analysis, Gemini ID validation, caching, cool-down and fallback;
- detail pages, including when TMDB fails;
- ratings, reviews, watchlists, profiles and lists, including permissions;
- the TMDB importer.

## Production notes

Set `DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, then
collect static files. With debug off, WhiteNoise serves the compressed,
manifest-hashed static files.

```bash
python manage.py collectstatic --noinput
```
