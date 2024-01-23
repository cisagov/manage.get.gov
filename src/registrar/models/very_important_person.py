from django.db import models

from .utility.time_stamped_model import TimeStampedModel


class VeryImportantPerson(TimeStampedModel):

    """"""

    email = models.EmailField(
        null=False,
        blank=True,
        help_text="Email",
        db_index=True,
    )

    requestor = models.ForeignKey(
        "registrar.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verifiedby_user",
    )

    notes = models.TextField(
        null=False,
        blank=True,
        help_text="Notes",
    )

    def __str__(self):
        return self.email
