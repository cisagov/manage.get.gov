from django.db import models

from registrar.models.domain_request import DomainRequest
from registrar.models.federal_agency import FederalAgency
from registrar.models.utility.portfolio_helper import UserPortfolioRoleChoices
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
        help_text="Associated user",
        related_name="created_portfolios",
        unique=False,
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
        help_text="Associated senior official",
        unique=False,
        null=True,
        blank=True,
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

    # == Getters for users == #
    def get_users(self):
        """Returns all users associated with this portfolio"""
        return self.portfolio_users.all()

    def get_administrators(self):
        """Returns all administrators associated with this portfolio"""
        return self.portfolio_users.filter(
            portfolio_roles__overlap=[
                UserPortfolioRoleChoices.ORGANIZATION_ADMIN,
            ]
        )
    
    def get_readonly_administrators(self):
        """Returns all readonly_administrators associated with this portfolio"""
        return self.portfolio_users.filter(
            portfolio_roles__overlap=[
                UserPortfolioRoleChoices.ORGANIZATION_ADMIN_READ_ONLY,
            ]
        )

    def get_members(self):
        """Returns all members associated with this portfolio"""
        return self.portfolio_users.filter(
            portfolio_roles__overlap=[
                UserPortfolioRoleChoices.ORGANIZATION_MEMBER,
            ]
        )
