import logging

from django.db import models

from .utility.time_stamped_model import TimeStampedModel
from .domain_request import DomainRequest
from phonenumber_field.modelfields import PhoneNumberField  # type: ignore

logger = logging.getLogger(__name__)


class FederalTribe(TimeStampedModel):

    StateTerritoryChoices = DomainRequest.StateTerritoryChoices

    tribe_full_name = models.CharField(
        unique=True,
        verbose_name="Tribe full name",
        help_text="Full official name of the federally recognized tribe",
    )
    tribe = models.CharField(
        null=True,
        blank=True,
        help_text="Shortened tribe name",
    )
    tribe_alternate_name = models.CharField(
        null=True,
        blank=True,
    )
    # Tribal contact information
    first_name = models.CharField(
        null=True,
        blank=True,
    )
    last_name = models.CharField(
        null=True,
        blank=True,
    )
    suffix = models.CharField(
        null=True,
        blank=True,
        help_text="Name suffix (ie jr, sr, III)",
    )
    # Preferred name or nickname of contact (Also Known As)
    aka = models.CharField(
        null=True,
        blank=True,
        verbose_name="AKA",
    )
    job_title = models.CharField(
        null=True,
        blank=True,
    )
    organization = models.CharField(
        null=True,
        blank=True,
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
    phone = PhoneNumberField(
        null=True,
        blank=True,
    )
    email = models.EmailField(
        max_length=320,
        null=True,
        blank=True,
    )
    website = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )
    date_elected = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date elected",
    )
    next_election = models.DateField(
        null=True,
        blank=True,
        verbose_name="Next election",
    )
    notes = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Federal tribe"
        verbose_name_plural = "Federal tribes"
        ordering = ["tribe_full_name"]

    def __str__(self):
        return self.tribe_full_name or ""
