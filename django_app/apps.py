from django.apps import AppConfig
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views import View


class DjangoAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'django_app'
    verbose_name = 'Movie rating'

    def ready(self):
        import django_app.signals

