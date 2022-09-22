from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    A custom user model that performs identically to the default user model
    but can be customized later.
    """

    def __str__(self):
        if self.userprofile.display_name:
            return self.userprofile.display_name
        else:
            return self.username


class TimeStampedModel(models.Model):
    """
    An abstract base model that provides self-updating
    `created_at` and `updated_at` fields.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        # don't put anything else here, it will be ignored


class AddressModel(models.Model):
    """
    An abstract base model that provides common fields
    for postal addresses.
    """

    # contact's street (null ok)
    street1 = models.TextField(blank=True)
    # contact's street (null ok)
    street2 = models.TextField(blank=True)
    # contact's street (null ok)
    street3 = models.TextField(blank=True)
    # contact's city
    city = models.TextField(blank=True)
    # contact's state or province (null ok)
    sp = models.TextField(blank=True)
    # contact's postal code (null ok)
    pc = models.TextField(blank=True)
    # contact's country code
    cc = models.TextField(blank=True)

    class Meta:
        abstract = True
        # don't put anything else here, it will be ignored


class ContactModel(models.Model):
    """
    An abstract base model that provides common fields
    for contact information.
    """

    voice = models.TextField(blank=True)
    fax = models.TextField(blank=True)
    email = models.TextField(blank=True)

    class Meta:
        abstract = True
        # don't put anything else here, it will be ignored


class UserProfile(TimeStampedModel, ContactModel, AddressModel):
    user = models.OneToOneField(User, null=True, on_delete=models.CASCADE)
    display_name = models.TextField()

    def __str__(self):
        if self.display_name:
            return self.display_name
        else:
            return self.user.username
