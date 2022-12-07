from django.db import models

from .utility.time_stamped_model import TimeStampedModel
from .utility.address_model import AddressModel

from .contact import Contact


class UserProfile(TimeStampedModel, Contact, AddressModel):

    """User information, unrelated to their login/auth details."""

    user = models.OneToOneField(
        "registrar.User",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    display_name = models.TextField()

    def __str__(self):
        # use info stored in User rather than Contact,
        # because Contact is user-editable while User
        # pulls from identity-verified Login.gov
        try:
            return str(self.user)
        except Exception:
            return "Orphaned account"
