from django.contrib.auth.models import Group

class UserGroup(Group):
    # Add custom fields or methods specific to your group model here

    class Meta:
        verbose_name = "User group"
        verbose_name_plural = "User groups"