"""Non-destructive data migration.

* Creates Genre rows and links every existing title to the genres stored in
  the legacy comma-separated ``genre`` column (the column itself is kept).
* Fills ``media_type`` from the category.
* Creates a profile for any user that doesn't have one yet.
"""
from django.db import migrations

GENRE_NAMES = {
    'action': 'Action', 'adventure': 'Adventure', 'animation': 'Animation', 'comedy': 'Comedy',
    'crime': 'Crime', 'documentary': 'Documentary', 'drama': 'Drama', 'family': 'Family',
    'fantasy': 'Fantasy', 'history': 'History', 'horror': 'Horror', 'kids': 'Kids',
    'music': 'Music', 'mystery': 'Mystery', 'romance': 'Romance', 'sci-fi': 'Sci-fi',
    'thriller': 'Thriller', 'war': 'War', 'western': 'Western', 'reality': 'Reality',
    'tv-movie': 'TV Movie',
}
ALIASES = {'scifi': 'sci-fi', 'science fiction': 'sci-fi', 'sci fi': 'sci-fi', 'фантастика': 'sci-fi'}


def forwards(apps, schema_editor):
    Genre = apps.get_model('django_app', 'Genre')
    Cinematography = apps.get_model('django_app', 'Cinematography')
    Profile = apps.get_model('django_app', 'profile')
    User = apps.get_model('auth', 'User')

    genres = {}
    for slug, name in GENRE_NAMES.items():
        genres[slug], _ = Genre.objects.get_or_create(slug=slug, defaults={'name': name})

    for title in Cinematography.objects.all().iterator():
        slugs = []
        for raw in (title.genre or '').split(','):
            slug = ALIASES.get(raw.strip().lower(), raw.strip().lower())
            if not slug or slug == 'none':
                continue
            if slug not in genres:
                genres[slug], _ = Genre.objects.get_or_create(
                    slug=slug[:40], defaults={'name': slug.replace('-', ' ').title()[:60]})
            slugs.append(slug)
        if slugs:
            title.genres.add(*[genres[s] for s in slugs])
        if not title.media_type:
            media = 'tv' if title.category in ('series', 'anime') else 'movie'
            Cinematography.objects.filter(pk=title.pk).update(media_type=media)

    for user in User.objects.filter(profile__isnull=True):
        Profile.objects.create(user=user)


class Migration(migrations.Migration):

    dependencies = [
        ('django_app', '0020_catalog_genres_ratings_watchlists'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
