import logging

from django.db import models
from django.contrib.postgres.fields import ArrayField


from .utility.time_stamped_model import TimeStampedModel
from .domain_request import DomainRequest
from phonenumber_field.modelfields import PhoneNumberField  # type: ignore

logger = logging.getLogger(__name__)


class StateTribe(TimeStampedModel):

    StateTerritoryChoices = DomainRequest.StateTerritoryChoices

    tribe_name = models.CharField(
        unique=True,
    )
    recognized_state = models.CharField(
        max_length=2,
        choices=StateTerritoryChoices.choices,  # type: ignore[misc]
        null=True,
        blank=True,
        verbose_name="Recognized State",
    )
    authorizing_legislation = models.URLField(
        max_length=255,
        null=True,
        blank=True,
    )
    tribal_leader_first_name = models.CharField(
        null=True,
        blank=True,
    )
    tribal_leader_last_name = models.CharField(
        null=True,
        blank=True,
    )
    suffix = models.CharField(
        null=True,
        blank=True,
        help_text="Name suffix (ie jr, sr, III)",
    )
    evidence_of_tribal_leader_designation = models.TextField(
        null=True,
        blank=True,
    )
    email = ArrayField(
        models.EmailField(max_length=320),
        null=True,
        blank=True,
        default=list,
        help_text="List of email addresses for the tribal leader or designated contact",
    )
    phone = PhoneNumberField(
        null=True,
        blank=True,
        help_text="Phone number for the tribal leader or designated contact",
    )
    website = models.URLField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Tribe's official website",
    )
    address_line1 = models.CharField(
        null=True,
        blank=True,
        verbose_name="address line 1",
    )
    address_line2 = models.CharField(
        null=True,
        blank=True,
        verbose_name="address line 2",
    )
    city = models.CharField(
        null=True,
        blank=True,
    )
    state_territory = models.CharField(
        max_length=2,
        choices=StateTerritoryChoices.choices,  # type: ignore[misc]
        null=True,
        blank=True,
        verbose_name="State, Territory, or Military Post",
    )
    zipcode = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        verbose_name="Zip code",
    )
    urbanization = models.CharField(
        null=True,
        blank=True,
    )
    date_of_recognition = models.DateField(
        null=True,
        blank=True,
    )
    additional_sources = models.TextField(
        null=True,
        blank=True,
    )
    notes = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "State tribe"
        verbose_name_plural = "State tribes"
        ordering = ["tribe_name"]

    def __str__(self):
        return self.tribe_name or ""
