from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver

from .models import UserProfile


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
