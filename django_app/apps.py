from django.apps import AppConfig


class DjangoAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'django_app'
    verbose_name = 'Movie rating'

    def ready(self):
        from . import signals  # noqa: F401
