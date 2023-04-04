import logging

from django.contrib.auth.models import AbstractUser
from django.db import models

from .domain_invitation import DomainInvitation

from phonenumber_field.modelfields import PhoneNumberField  # type: ignore


logger = logging.getLogger(__name__)


class User(AbstractUser):
    """
    A custom user model that performs identically to the default user model
    but can be customized later.
    """

    domains = models.ManyToManyField(
        "registrar.Domain",
        through="registrar.UserDomainRole",
        related_name="users",
    )

    phone = PhoneNumberField(
        null=True,
        blank=True,
        help_text="Phone",
        db_index=True,
    )

    def __str__(self):
        # this info is pulled from Login.gov
        if self.first_name or self.last_name:
            return f"{self.first_name or ''} {self.last_name or ''}"
        elif self.email:
            return self.email
        else:
            return self.username

    def first_login(self):
        """Callback when the user is authenticated for the very first time.

        When a user first arrives on the site, we need to retrieve any domain
        invitations that match their email address.
        """
        for invitation in DomainInvitation.objects.filter(
            email=self.email, status=DomainInvitation.INVITED
        ):
            try:
                invitation.retrieve()
                invitation.save()
            except RuntimeError:
                # retrieving should not fail because of a missing user, but
                # if it does fail, log the error so a new user can continue
                # logging in
                logger.warn("Failed to retrieve invitation %s", invitation,  exc_info=True)
