from django.db import models

from registrar.models.domain_request import DomainRequest
from registrar.models.federal_agency import FederalAgency
from registrar.utility.constants import BranchChoices

from .utility.time_stamped_model import TimeStampedModel


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
    creator = models.ForeignKey(
        "registrar.User",
        on_delete=models.PROTECT,
        verbose_name="Portfolio creator",
        related_name="created_portfolios",
        unique=False,
    )

    # Q for reviewers: shouldn't this be a required field?
    organization_name = models.CharField(
        null=True,
        blank=True,
        verbose_name="Portfolio organization",
    )

    organization_type = models.CharField(
        max_length=255,
        choices=OrganizationChoices.choices,
        null=True,
        blank=True,
        help_text="Type of organization",
    )

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

    federal_type = models.CharField(
        max_length=50,
        choices=BranchChoices.choices,
        null=True,
        blank=True,
    )

    senior_official = models.ForeignKey(
        "registrar.SeniorOfficial",
        on_delete=models.PROTECT,
        unique=False,
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
        return str(self.organization_name)

    @property
    def portfolio_type(self):
        """
        Returns a combination of organization_type / federal_type, seperated by ' - '.
        If no federal_type is found, we just return the org type."""
        org_type = self.OrganizationChoices.get_org_label(self.organization_type)
        if self.organization_type == self.OrganizationChoices.FEDERAL and self.federal_type:
            return " - ".join([org_type, self.federal_type])
        else:
            return org_type

    # == Getters for domains == #
    def get_domains(self):
        """Returns all DomainInformations associated with this portfolio"""
        return self.information_portfolio.all()

    def get_domain_requests(self):
        """Returns all DomainRequests associated with this portfolio"""
        return self.DomainRequest_portfolio.all()

    # == Getters for suborganization == #
    def get_suborganizations(self):
        """Returns all suborganizations associated with this portfolio"""
        return self.portfolio_suborganizations.all()
