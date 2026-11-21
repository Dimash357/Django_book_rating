from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import profile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        profile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, created, raw=False, **kwargs):
    if raw or created:
        return
    # Users created before profiles existed (e.g. early superusers) get one lazily.
    user_profile, _ = profile.objects.get_or_create(user=instance)
