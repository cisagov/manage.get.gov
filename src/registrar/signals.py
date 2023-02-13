import logging

from django.conf import settings
from django.core.management import call_command
from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver

from .models import User, UserProfile


logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def handle_profile(sender, instance, **kwargs):
    """Method for when a User is saved.

    If the user is being created, then create a matching UserProfile. Otherwise
    save an updated profile or create one if it doesn't exist.
    """

    if kwargs.get("created", False):
        UserProfile.objects.create(user=instance)
    else:
        # the user is not being created.
        if hasattr(instance, "userprofile"):
            instance.userprofile.save()
        else:
            UserProfile.objects.create(user=instance)


@receiver(post_migrate)
def handle_loaddata(**kwargs):
    """Attempt to load test fixtures when in DEBUG mode."""
    if settings.DEBUG:
        try:
            call_command("load")
        except Exception as e:
            logger.warning(e)
