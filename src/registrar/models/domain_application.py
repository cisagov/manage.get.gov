from __future__ import annotations
from typing import TYPE_CHECKING, Union

from django.apps import apps
from django.db import models
from django_fsm import FSMField, transition  # type: ignore

from .utility.time_stamped_model import TimeStampedModel

if TYPE_CHECKING:
    from ..forms.application_wizard import ApplicationWizard


class DomainApplication(TimeStampedModel):

    """A registrant's application for a new domain."""

    # #### Contants for choice fields ####
    STARTED = "started"
    SUBMITTED = "submitted"
    INVESTIGATING = "investigating"
    APPROVED = "approved"
    STATUS_CHOICES = [
        (STARTED, STARTED),
        (SUBMITTED, SUBMITTED),
        (INVESTIGATING, INVESTIGATING),
        (APPROVED, APPROVED),
    ]

    class StateTerritoryChoices(models.TextChoices):
        ALABAMA = "AL", "Alabama"
        ALASKA = "AK", "Alaska"
        ARIZONA = "AZ", "Arizona"
        ARKANSAS = "AR", "Arkansas"
        CALIFORNIA = "CA", "California"
        COLORADO = "CO", "Colorado"
        CONNECTICUT = "CT", "Connecticut"
        DELAWARE = "DE", "Delaware"
        DISTRICT_OF_COLUMBIA = "DC", "District of Columbia"
        FLORIDA = "FL", "Florida"
        GEORGIA = "GA", "Georgia"
        HAWAII = "HI", "Hawaii"
        IDAHO = "ID", "Idaho"
        ILLINOIS = "IL", "Illinois"
        INDIANA = "IN", "Indiana"
        IOWA = "IA", "Iowa"
        KANSAS = "KS", "Kansas"
        KENTUCKY = "KY", "Kentucky"
        LOUISIANA = "LA", "Louisiana"
        MAINE = "ME", "Maine"
        MARYLAND = "MD", "Maryland"
        MASSACHUSETTS = "MA", "Massachusetts"
        MICHIGAN = "MI", "Michigan"
        MINNESOTA = "MN", "Minnesota"
        MISSISSIPPI = "MS", "Mississippi"
        MISSOURI = "MO", "Missouri"
        MONTANA = "MT", "Montana"
        NEBRASKA = "NE", "Nebraska"
        NEVADA = "NV", "Nevada"
        NEW_HAMPSHIRE = "NH", "New Hampshire"
        NEW_JERSEY = "NJ", "New Jersey"
        NEW_MEXICO = "NM", "New Mexico"
        NEW_YORK = "NY", "New York"
        NORTH_CAROLINA = "NC", "North Carolina"
        NORTH_DAKOTA = "ND", "North Dakota"
        OHIO = "OH", "Ohio"
        OKLAHOMA = "OK", "Oklahoma"
        OREGON = "OR", "Oregon"
        PENNSYLVANIA = "PA", "Pennsylvania"
        RHODE_ISLAND = "RI", "Rhode Island"
        SOUTH_CAROLINA = "SC", "South Carolina"
        SOUTH_DAKOTA = "SD", "South Dakota"
        TENNESSEE = "TN", "Tennessee"
        TEXAS = "TX", "Texas"
        UTAH = "UT", "Utah"
        VERMONT = "VT", "Vermont"
        VIRGINIA = "VA", "Virginia"
        WASHINGTON = "WA", "Washington"
        WEST_VIRGINIA = "WV", "West Virginia"
        WISCONSIN = "WI", "Wisconsin"
        WYOMING = "WY", "Wyoming"
        AMERICAN_SAMOA = "AS", "American Samoa"
        GUAM = "GU", "Guam"
        NORTHERN_MARIANA_ISLANDS = "MP", "Northern Mariana Islands"
        PUERTO_RICO = "PR", "Puerto Rico"
        VIRGIN_ISLANDS = "VI", "Virgin Islands"

    class OrganizationChoices(models.TextChoices):
        FEDERAL = "federal", "Federal: a federal agency"
        INTERSTATE = "interstate", "Interstate: an organization of two or more states"
        STATE_OR_TERRITORY = "state_or_territory", (
            "State or Territory: One of the 50 U.S. states, the District of "
            "Columbia, American Samoa, Guam, Northern Mariana Islands, "
            "Puerto Rico, or the U.S. Virgin Islands"
        )
        TRIBAL = "tribal", (
            "Tribal: a tribal government recognized by the federal or "
            "state government"
        )
        COUNTY = "county", "County: a county, parish, or borough"
        CITY = "city", "City: a city, town, township, village, etc."
        SPECIAL_DISTRICT = "special_district", (
            "Special District: an independent organization within a single state"
        )

    class BranchChoices(models.TextChoices):
        EXECUTIVE = "executive", "Executive"
        JUDICIAL = "judicial", "Judicial"
        LEGISLATIVE = "legislative", "Legislative"

    # #### Internal fields about the application #####
    status = FSMField(
        choices=STATUS_CHOICES,  # possible states as an array of constants
        default=STARTED,  # sensible default
        protected=False,  # can change state directly, particularly in Django admin
    )
    # This is the application user who created this application. The contact
    # information that they gave is in the `submitter` field
    creator = models.ForeignKey(
        "registrar.User",
        on_delete=models.PROTECT,
        related_name="applications_created",
    )
    investigator = models.ForeignKey(
        "registrar.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="applications_investigating",
    )

    # ##### data fields from the initial form #####
    organization_type = models.CharField(
        max_length=255,
        choices=OrganizationChoices.choices,
        null=True,
        blank=True,
        help_text="Type of Organization",
    )

    federal_type = models.CharField(
        max_length=50,
        choices=BranchChoices.choices,
        null=True,
        blank=True,
        help_text="Branch of federal government",
    )

    is_election_board = models.BooleanField(
        null=True,
        blank=True,
        help_text="Is your ogranization an election office?",
    )

    organization_name = models.TextField(
        null=True,
        blank=True,
        help_text="Organization name",
        db_index=True,
    )
    address_line1 = models.TextField(
        null=True,
        blank=True,
        help_text="Address line 1",
    )
    address_line2 = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        help_text="Address line 2",
    )
    state_territory = models.CharField(
        max_length=2,
        null=True,
        blank=True,
        help_text="State/Territory",
    )
    zipcode = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text="ZIP code",
        db_index=True,
    )

    authorizing_official = models.ForeignKey(
        "registrar.Contact",
        null=True,
        blank=True,
        related_name="authorizing_official",
        on_delete=models.PROTECT,
    )

    # "+" means no reverse relation to lookup applications from Website
    current_websites = models.ManyToManyField(
        "registrar.Website",
        blank=True,
        related_name="current+",
    )

    requested_domain = models.OneToOneField(
        "Domain",
        null=True,
        blank=True,
        help_text="The requested domain",
        related_name="domain_application",
        on_delete=models.PROTECT,
    )
    alternative_domains = models.ManyToManyField(
        "registrar.Website",
        blank=True,
        related_name="alternatives+",
    )

    # This is the contact information provided by the applicant. The
    # application user who created it is in the `creator` field.
    submitter = models.ForeignKey(
        "registrar.Contact",
        null=True,
        blank=True,
        related_name="submitted_applications",
        on_delete=models.PROTECT,
    )

    purpose = models.TextField(
        null=True,
        blank=True,
        help_text="Purpose of the domain",
    )

    other_contacts = models.ManyToManyField(
        "registrar.Contact",
        blank=True,
        related_name="contact_applications",
    )

    security_email = models.CharField(
        max_length=320,
        null=True,
        blank=True,
        help_text="Security email for public use",
    )

    anything_else = models.TextField(
        null=True,
        blank=True,
        help_text="Anything else we should know?",
    )

    is_policy_acknowledged = models.BooleanField(
        null=True,
        blank=True,
        help_text="Acknowledged .gov acceptable use policy",
    )

    def __str__(self):
        try:
            if self.requested_domain and self.requested_domain.name:
                return self.requested_domain.name
            else:
                return f"{self.status} application created by {self.creator}"
        except Exception:
            return ""

    @transition(field="status", source=STARTED, target=SUBMITTED)
    def submit(self):
        """Submit an application that is started."""

        # check our conditions here inside the `submit` method so that we
        # can raise more informative exceptions

        # requested_domain could be None here
        if not hasattr(self, "requested_domain"):
            raise ValueError("Requested domain is missing.")

        if self.requested_domain is None:
            raise ValueError("Requested domain is missing.")

        Domain = apps.get_model("registrar.Domain")
        if not Domain.string_could_be_domain(self.requested_domain.name):
            raise ValueError("Requested domain is not a valid domain name.")

        # if no exception was raised, then we don't need to do anything
        # inside this method, keep the `pass` here to remind us of that
        pass

    # ## Form policies ###
    #
    # These methods control what questions need to be answered by applicants
    # during the application flow. They are policies about the application so
    # they appear here.

    @staticmethod
    def _get_organization_type(wizard: ApplicationWizard) -> Union[str, None]:
        """Extract the answer to the organization type question from the wizard."""
        # using the step data from the storage is a workaround for this
        # bug in django-formtools version 2.4
        # https://github.com/jazzband/django-formtools/issues/220
        type_data = wizard.storage.get_step_data("organization_type")
        if type_data:
            return type_data.get("organization_type-organization_type")
        return None

    @staticmethod
    def show_organization_federal(wizard: ApplicationWizard) -> bool:
        """Show this step if the answer to the first question was "federal"."""
        user_choice = DomainApplication._get_organization_type(wizard)
        return user_choice == DomainApplication.OrganizationChoices.FEDERAL

    @staticmethod
    def show_organization_election(wizard: ApplicationWizard) -> bool:
        """Show this step if the answer to the first question implies it.

        This shows for answers that aren't "Federal" or "Interstate".
        """
        user_choice = DomainApplication._get_organization_type(wizard)
        excluded = [
            DomainApplication.OrganizationChoices.FEDERAL,
            DomainApplication.OrganizationChoices.INTERSTATE,
        ]
        return bool(user_choice and user_choice not in excluded)
