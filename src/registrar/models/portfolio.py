from django.db import models

from registrar.models.domain_request import DomainRequest
from registrar.models.federal_agency import FederalAgency

from .utility.time_stamped_model import TimeStampedModel


def get_default_federal_agency():
    """returns non-federal agency"""
    return FederalAgency.objects.filter(agency="Non-Federal Agency").first()


class Portfolio(TimeStampedModel):
    """
    Portfolio is used for organizing domains/domain-requests into
    manageable groups.
    """

    # use the short names in Django admin
    OrganizationChoices = DomainRequest.OrganizationChoices
    StateTerritoryChoices = DomainRequest.StateTerritoryChoices

    # creator - stores who created this model. If no creator is specified in DJA,
    # then the creator will default to the current request user"""
    creator = models.ForeignKey("registrar.User", on_delete=models.PROTECT, help_text="Associated user", unique=False)

    # notes - text field (copies what is done on domain requests)
    notes = models.TextField(
        null=True,
        blank=True,
    )

    # federal agency - FK to fed agency table (Not nullable, should default
    # to the Non-federal agency value in the fed agency table)
    federal_agency = models.ForeignKey(
        "registrar.FederalAgency",
        on_delete=models.PROTECT,
        help_text="Associated federal agency",
        unique=False,
        default=get_default_federal_agency,
    )

    # organization type - should match organization types allowed on domain info
    organization_type = models.CharField(
        max_length=255,
        choices=OrganizationChoices.choices,
        null=True,
        blank=True,
        help_text="Type of organization",
    )

    # organization name
    # NOTE: org name will be the same as federal agency, if it is federal,
    # otherwise it will be the actual org name. If nothing is entered for
    # org name and it is a federal organization, have this field fill with
    # the federal agency text name.
    organization_name = models.CharField(
        null=True,
        blank=True,
    )

    # address_line1
    address_line1 = models.CharField(
        null=True,
        blank=True,
        verbose_name="address line 1",
    )
    # address_line2
    address_line2 = models.CharField(
        null=True,
        blank=True,
        verbose_name="address line 2",
    )
    # city
    city = models.CharField(
        null=True,
        blank=True,
    )
    # state (copied from domain_request.py -- imports enums from domain_request.py)
    state_territory = models.CharField(
        max_length=2,
        choices=StateTerritoryChoices.choices,
        null=True,
        blank=True,
        verbose_name="state / territory",
    )
    # zipcode
    zipcode = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        verbose_name="zip code",
    )
    # urbanization
    urbanization = models.CharField(
        null=True,
        blank=True,
        help_text="Required for Puerto Rico only",
        verbose_name="urbanization",
    )

    # security_contact_email
    security_contact_email = models.EmailField(
        null=True,
        blank=True,
        verbose_name="security contact e-mail",
        max_length=320,
    )
