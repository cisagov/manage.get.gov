from __future__ import annotations

from django.db import models
from django_fsm import FSMField, transition  # type: ignore

from .utility.time_stamped_model import TimeStampedModel
from .contact import Contact
from .user import User
from .website import Website

from typing import TYPE_CHECKING, Union

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

    FEDERAL = "federal"
    INTERSTATE = "interstate"
    STATE_OR_TERRITORY = "state_or_territory"
    TRIBAL = "tribal"
    COUNTY = "county"
    CITY = "city"
    SPECIAL_DISTRICT = "special_district"
    ORGANIZATION_CHOICES = [
        (FEDERAL, "a federal agency"),
        (INTERSTATE, "an organization of two or more states"),
        (
            STATE_OR_TERRITORY,
            "one of the 50 U.S. states, the District of "
            "Columbia, American Samoa, Guam, Northern Mariana Islands, "
            "Puerto Rico, or the U.S. Virgin Islands",
        ),
        (
            TRIBAL,
            "a tribal government recognized by the federal or " "state government",
        ),
        (COUNTY, "a county, parish, or borough"),
        (CITY, "a city, town, township, village, etc."),
        (SPECIAL_DISTRICT, "an independent organization within a single state"),
    ]

    EXECUTIVE = "Executive"
    JUDICIAL = "Judicial"
    LEGISLATIVE = "Legislative"
    BRANCH_CHOICES = [(x, x) for x in (EXECUTIVE, JUDICIAL, LEGISLATIVE)]

    # #### Internal fields about the application #####
    status = FSMField(
        choices=STATUS_CHOICES,  # possible states as an array of constants
        default=STARTED,  # sensible default
        protected=False,  # can change state directly, particularly in Django admin
    )
    # This is the application user who created this application. The contact
    # information that they gave is in the `submitter` field
    creator = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="applications_created"
    )
    investigator = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="applications_investigating",
    )

    # ##### data fields from the initial form #####
    organization_type = models.CharField(
        max_length=255,
        choices=ORGANIZATION_CHOICES,
        null=True,
        blank=True,
        help_text="Type of Organization",
    )

    federal_branch = models.CharField(
        max_length=50,
        choices=BRANCH_CHOICES,
        null=True,
        blank=True,
        help_text="Branch of federal government",
    )

    is_election_office = models.BooleanField(
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
    street_address = models.TextField(
        null=True,
        blank=True,
        help_text="Street Address",
    )
    unit_type = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        help_text="Unit type",
    )
    unit_number = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Unit number",
    )
    state_territory = models.CharField(
        max_length=2,
        null=True,
        blank=True,
        help_text="State/Territory",
    )
    zip_code = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text="ZIP code",
        db_index=True,
    )

    authorizing_official = models.ForeignKey(
        Contact,
        null=True,
        blank=True,
        related_name="authorizing_official",
        on_delete=models.PROTECT,
    )

    # "+" means no reverse relation to lookup applications from Website
    current_websites = models.ManyToManyField(
        Website,
        blank=True,
        related_name="current+",
    )

    requested_domain = models.ForeignKey(
        Website,
        null=True,
        blank=True,
        help_text="The requested domain",
        related_name="requested+",
        on_delete=models.PROTECT,
    )
    alternative_domains = models.ManyToManyField(
        Website,
        blank=True,
        related_name="alternatives+",
    )

    # This is the contact information provided by the applicant. The
    # application user who created it is in the `creator` field.
    submitter = models.ForeignKey(
        Contact,
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
        Contact,
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

    acknowledged_policy = models.BooleanField(
        null=True,
        blank=True,
        help_text="Acknowledged .gov acceptable use policy",
    )

    def __str__(self):
        try:
            if self.requested_domain and self.requested_domain.website:
                return self.requested_domain.website
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
        if (not self.requested_domain) or (not self.requested_domain.could_be_domain()):
            raise ValueError("Requested domain is not a legal domain name.")

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
        return DomainApplication._get_organization_type(wizard) == "Federal"

    @staticmethod
    def show_organization_election(wizard: ApplicationWizard) -> bool:
        """Show this step if the answer to the first question implies it.

        This shows for answers that aren't "Federal" or "Interstate".
        """
        type_answer = DomainApplication._get_organization_type(wizard)
        if type_answer and type_answer not in ("Federal", "Interstate"):
            return True
        return False
