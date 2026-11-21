from django.contrib import admin

from .models import Cinematography, Genre, Rating, Review, UserList, WatchlistEntry, profile


@admin.register(Cinematography)
class CinematographyAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'release_date', 'tmdb_rating', 'popularity', 'tmdb_id')
    list_filter = ('category', 'genres', 'media_type')
    search_fields = ('title', 'original_title', 'description')
    filter_horizontal = ('genres',)
    date_hierarchy = 'release_date'


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ('user', 'item', 'score', 'updated_at')
    list_filter = ('score',)
    search_fields = ('user__username', 'item__title')
    raw_id_fields = ('user', 'item')


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'item', 'contains_spoilers', 'updated_at')
    search_fields = ('user__username', 'item__title', 'text')
    raw_id_fields = ('user', 'item')


@admin.register(WatchlistEntry)
class WatchlistEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'item', 'status', 'updated_at')
    list_filter = ('status',)
    search_fields = ('user__username', 'item__title')
    raw_id_fields = ('user', 'item')


@admin.register(UserList)
class UserListAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'is_public', 'updated_at')
    search_fields = ('name', 'user__username')
    raw_id_fields = ('user', 'items')


admin.site.register(profile)
