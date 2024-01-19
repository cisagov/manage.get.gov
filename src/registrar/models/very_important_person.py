from django.db import models

from .utility.time_stamped_model import TimeStampedModel


class VeryImportantPerson(TimeStampedModel):

    """"""

    email = models.EmailField(
        null=True,
        blank=True,
        help_text="Email",
        db_index=True,
    )

    user = models.ForeignKey(
        "registrar.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verifiedby_user",
    )

    notes = models.TextField(
        null=True,
        blank=True,
        help_text="Notes",
    )

    def __str__(self):
        try:
            if self.email:
                return self.email
        except Exception:
            return ""
