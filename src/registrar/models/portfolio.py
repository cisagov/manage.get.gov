from django.db import models

from registrar.models.domain_request import DomainRequest
from registrar.models.federal_agency import FederalAgency

from .utility.time_stamped_model import TimeStampedModel


# def get_default_federal_agency():
#     """returns non-federal agency"""
#     return FederalAgency.objects.filter(agency="Non-Federal Agency").first()


class Portfolio(TimeStampedModel):
    """
    Portfolio is used for organizing domains/domain-requests into
    manageable groups.
    """

    # use the short names in Django admin
    OrganizationChoices = DomainRequest.OrganizationChoices
    StateTerritoryChoices = DomainRequest.StateTerritoryChoices

    # Stores who created this model. If no creator is specified in DJA,
    # then the creator will default to the current request user"""
    creator = models.ForeignKey("registrar.User", on_delete=models.PROTECT, help_text="Associated user", unique=False)

    notes = models.TextField(
        null=True,
        blank=True,
    )

    federal_agency = models.ForeignKey(
        "registrar.FederalAgency",
        on_delete=models.PROTECT,
        help_text="Associated federal agency",
        unique=False,
        default=FederalAgency.get_non_federal_agency,
    )

    organization_type = models.CharField(
        max_length=255,
        choices=OrganizationChoices.choices,
        null=True,
        blank=True,
        help_text="Type of organization",
    )

    organization_name = models.CharField(
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

    # (imports enums from domain_request.py)
    state_territory = models.CharField(
        max_length=2,
        choices=StateTerritoryChoices.choices,
        null=True,
        blank=True,
        verbose_name="state / territory",
    )

    zipcode = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        verbose_name="zip code",
    )

    urbanization = models.CharField(
        null=True,
        blank=True,
        help_text="Required for Puerto Rico only",
        verbose_name="urbanization",
    )

    security_contact_email = models.EmailField(
        null=True,
        blank=True,
        verbose_name="security contact e-mail",
        max_length=320,
    )

    def __str__(self) -> str:
        return f"{self.organization_name}"
