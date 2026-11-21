import datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Count, Q
from django.urls import reverse


class Genre(models.Model):
    """A genre; a title may have many genres (TMDB style)."""

    slug = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=60)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class CinematographyQuerySet(models.QuerySet):
    def with_user_stats(self):
        return self.annotate(
            user_avg=Avg('ratings__score'),
            user_votes=Count('ratings', distinct=True),
        )


class Cinematography(models.Model):
    CATEGORY_CHOICES = [
        ('movie', 'Movie'),
        ('series', 'Series'),
        ('cartoons', 'Cartoons'),
        ('anime', 'Anime'),
    ]
    # Legacy genre choices, kept for backwards compatibility with old forms.
    GENRE_CHOICES = [
        ('action', 'Action'),
        ('comedy', 'Comedy'),
        ('drama', 'Drama'),
        ('fantasy', 'Fantasy'),
        ('horror', 'Horror'),
        ('romance', 'Romance'),
        ('sci-fi', 'Sci-fi'),
    ]
    MEDIA_MOVIE = 'movie'
    MEDIA_TV = 'tv'
    MEDIA_TYPE_CHOICES = [(MEDIA_MOVIE, 'Movie'), (MEDIA_TV, 'TV')]

    title = models.CharField(max_length=200, db_index=True)
    original_title = models.CharField(max_length=200, blank=True, default='')
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES, db_index=True)
    # Legacy comma-separated genre slugs; the ``genres`` M2M is the source of truth.
    genre = models.CharField(max_length=100, blank=True)
    genres = models.ManyToManyField(Genre, blank=True, related_name='titles')
    poster_path = models.CharField(max_length=255, blank=True, default='')
    backdrop_path = models.CharField(max_length=255, blank=True, default='')
    description = models.TextField()
    release_date = models.DateField(default=datetime.date.today, db_index=True)

    tmdb_id = models.PositiveIntegerField(null=True, blank=True)
    media_type = models.CharField(max_length=5, choices=MEDIA_TYPE_CHOICES, blank=True, default='')
    tmdb_rating = models.FloatField(null=True, blank=True)
    tmdb_vote_count = models.PositiveIntegerField(default=0)
    popularity = models.FloatField(default=0, db_index=True)
    original_language = models.CharField(max_length=10, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True, null=True)

    objects = CinematographyQuerySet.as_manager()

    class Meta:
        verbose_name = 'title'
        verbose_name_plural = 'titles'
        constraints = [
            models.UniqueConstraint(
                fields=['media_type', 'tmdb_id'],
                condition=Q(tmdb_id__isnull=False),
                name='unique_tmdb_title',
            ),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('django_app:title_detail', args=[self.pk])

    @property
    def tmdb_media_type(self):
        if self.media_type:
            return self.media_type
        return self.MEDIA_TV if self.category in ('series', 'anime') else self.MEDIA_MOVIE

    def _image(self, path, size):
        return f'{settings.TMDB_IMAGE_BASE}{size}{path}' if path else ''

    @property
    def poster_url(self):
        return self._image(self.poster_path, 'w500')

    @property
    def poster_thumb_url(self):
        return self._image(self.poster_path, 'w342')

    @property
    def backdrop_url(self):
        return self._image(self.backdrop_path, 'w1280')

    @property
    def tmdb_url(self):
        if not self.tmdb_id:
            return ''
        return f'https://www.themoviedb.org/{self.tmdb_media_type}/{self.tmdb_id}'

    @property
    def year(self):
        return self.release_date.year if self.release_date else None

    def sync_legacy_genre(self):
        """Keep the legacy CSV field in step with the M2M relation."""
        self.genre = ','.join(g.slug for g in self.genres.all())[:100]
        Cinematography.objects.filter(pk=self.pk).update(genre=self.genre)


class profile(models.Model):  # noqa: N801 - name kept for existing data/migrations
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='profile_images', default='profile_images/1.jpg')
    first = models.ImageField(upload_to='profile_images', default='')
    second = models.ImageField(upload_to='profile_images', default='')
    third = models.ImageField(upload_to='profile_images', default='')
    forth = models.ImageField(upload_to='profile_images', default='')
    description = models.TextField(default='')
    city = models.TextField(default='')

    def __str__(self):
        return f'{self.user.username}'

    @property
    def gallery(self):
        return [img for img in (self.first, self.second, self.third, self.forth) if img]


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Rating(TimeStamped):
    """A personal 1–10 rating; one per user and title."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings')
    item = models.ForeignKey(Cinematography, on_delete=models.CASCADE, related_name='ratings')
    score = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])

    class Meta:
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'item'], name='unique_user_rating'),
            models.CheckConstraint(condition=Q(score__gte=1) & Q(score__lte=10), name='rating_score_1_10'),
        ]

    def __str__(self):
        return f'{self.user} → {self.item}: {self.score}'


class Review(TimeStamped):
    """A written review; one per user and title (editable)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    item = models.ForeignKey(Cinematography, on_delete=models.CASCADE, related_name='reviews')
    text = models.TextField(max_length=5000)
    contains_spoilers = models.BooleanField(default=False)

    class Meta:
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'item'], name='unique_user_review'),
        ]

    def __str__(self):
        return f'Review by {self.user} on {self.item}'


class WatchlistEntry(TimeStamped):
    WATCHED = 'watched'
    WATCHING = 'watching'
    PLAN = 'plan'
    STATUS_CHOICES = [
        (WATCHING, 'Watching'),
        (PLAN, 'Plan to Watch'),
        (WATCHED, 'Watched'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='watchlist')
    item = models.ForeignKey(Cinematography, on_delete=models.CASCADE, related_name='watchlist_entries')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, db_index=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name_plural = 'watchlist entries'
        constraints = [
            models.UniqueConstraint(fields=['user', 'item'], name='unique_user_watchlist_item'),
        ]

    def __str__(self):
        return f'{self.user}: {self.item} ({self.get_status_display()})'


class UserList(TimeStamped):
    """A personal, named collection of titles."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lists')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, max_length=1000)
    is_public = models.BooleanField(default=True)
    items = models.ManyToManyField(Cinematography, blank=True, related_name='user_lists')

    class Meta:
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'name'], name='unique_user_list_name'),
        ]

    def __str__(self):
        return f'{self.name} ({self.user})'

    def get_absolute_url(self):
        return reverse('django_app:list_detail', args=[self.pk])
