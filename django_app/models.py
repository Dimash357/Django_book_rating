import datetime

from django.db import models
from django.contrib.auth.models import User


class Cinematography(models.Model):
    CATEGORY_CHOICES = [
        ('movie', 'Movie'),
        ('series', 'Series'),
        ('cartoons', 'Cartoons'),
        ('anime', 'Anime'),
    ]
    GENRE_CHOICES = [
        ('action', 'Action'),
        ('comedy', 'Comedy'),
        ('drama', 'Drama'),
        ('fantasy', 'Fantasy'),
        ('horror', 'Horror'),
        ('romance', 'Romance'),
        ('sci-fi', 'Sci-fi'),
    ]
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    genre = models.CharField(max_length=10, choices=GENRE_CHOICES)
    description = models.TextField()
    release_date = models.DateField(default=datetime.date.today)

    def __str__(self):
        return self.title

class profile(models.Model):
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
