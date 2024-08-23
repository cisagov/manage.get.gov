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

    # Addresses the UnorderedObjectListWarning
    class Meta:
        ordering = ["organization_name"]

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

    def save(self, *args, **kwargs):
        """Save override for custom properties"""

        # The urbanization field is only intended for the state_territory puerto rico
        if self.state_territory != self.StateTerritoryChoices.PUERTO_RICO and self.urbanization:
            self.urbanization = None

        super().save(*args, **kwargs)

    @property
    def portfolio_type(self):
        """
        Returns a combination of organization_type / federal_type, seperated by ' - '.
        If no federal_type is found, we just return the org type.
        """
        return self.get_portfolio_type(self.organization_type, self.federal_type)

    @classmethod
    def get_portfolio_type(cls, organization_type, federal_type):
        org_type_label = cls.OrganizationChoices.get_org_label(organization_type)
        agency_type_label = BranchChoices.get_branch_label(federal_type)
        if organization_type == cls.OrganizationChoices.FEDERAL and agency_type_label:
            return " - ".join([org_type_label, agency_type_label])
        else:
            return org_type_label

    @property
    def federal_type(self):
        """Returns the federal_type value on the underlying federal_agency field"""
        return self.get_federal_type(self.federal_agency)

    @classmethod
    def get_federal_type(cls, federal_agency):
        return federal_agency.federal_type if federal_agency else None

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
