from __future__ import annotations
from .domain_application import DomainApplication
from .utility.time_stamped_model import TimeStampedModel

import logging

from django.db import models


logger = logging.getLogger(__name__)


class DomainInformation(TimeStampedModel):

    """A registrant's domain information for that domain, exported from
    DomainApplication."""

    StateTerritoryChoices = DomainApplication.StateTerritoryChoices

    OrganizationChoices = DomainApplication.OrganizationChoices

    BranchChoices = DomainApplication.BranchChoices

    AGENCY_CHOICES = DomainApplication.AGENCY_CHOICES

    # This is the application user who created this application. The contact
    # information that they gave is in the `submitter` field
    creator = models.ForeignKey(
        "registrar.User",
        on_delete=models.PROTECT,
        related_name="information_created",
    )

    domain_application = models.OneToOneField(
        "registrar.DomainApplication",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="domainapplication_info",
        help_text="Associated domain application",
        unique=True,
    )

    # ##### data fields from the initial form #####
    organization_type = models.CharField(
        max_length=255,
        choices=OrganizationChoices.choices,
        null=True,
        blank=True,
        help_text="Type of Organization",
    )

    federally_recognized_tribe = models.BooleanField(
        null=True,
        help_text="Is the tribe federally recognized",
    )

    state_recognized_tribe = models.BooleanField(
        null=True,
        help_text="Is the tribe recognized by a state",
    )

    tribe_name = models.TextField(
        null=True,
        blank=True,
        help_text="Name of tribe",
    )

    federal_agency = models.TextField(
        null=True,
        blank=True,
        help_text="Federal agency",
    )

    federal_type = models.CharField(
        max_length=50,
        choices=BranchChoices.choices,
        null=True,
        blank=True,
        help_text="Federal government branch",
    )

    is_election_board = models.BooleanField(
        null=True,
        blank=True,
        help_text="Is your organization an election office?",
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
        help_text="Street address",
    )
    address_line2 = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        help_text="Street address line 2",
    )
    city = models.TextField(
        null=True,
        blank=True,
        help_text="City",
    )
    state_territory = models.CharField(
        max_length=2,
        null=True,
        blank=True,
        help_text="State, territory, or military post",
    )
    zipcode = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text="Zip code",
        db_index=True,
    )
    urbanization = models.TextField(
        null=True,
        blank=True,
        help_text="Urbanization (Puerto Rico only)",
    )

    type_of_work = models.TextField(
        null=True,
        blank=True,
        help_text="Type of work of the organization",
    )

    more_organization_information = models.TextField(
        null=True,
        blank=True,
        help_text="Further information about the government organization",
    )

    authorizing_official = models.ForeignKey(
        "registrar.Contact",
        null=True,
        blank=True,
        related_name="information_authorizing_official",
        on_delete=models.PROTECT,
    )

    domain = models.OneToOneField(
        "registrar.Domain",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        # Access this information via Domain as "domain.info"
        related_name="domain_info",
        help_text="Domain to which this information belongs",
    )

    # This is the contact information provided by the applicant. The
    # application user who created it is in the `creator` field.
    submitter = models.ForeignKey(
        "registrar.Contact",
        null=True,
        blank=True,
        related_name="submitted_applications_information",
        on_delete=models.PROTECT,
    )

    purpose = models.TextField(
        null=True,
        blank=True,
        help_text="Purpose of your domain",
    )

    other_contacts = models.ManyToManyField(
        "registrar.Contact",
        blank=True,
        related_name="contact_applications_information",
    )

    no_other_contacts_rationale = models.TextField(
        null=True,
        blank=True,
        help_text="Reason for listing no additional contacts",
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
    security_email = models.EmailField(
        max_length=320,
        null=True,
        blank=True,
        help_text="Security email for public use",
    )

    def __str__(self):
        try:
            if self.domain and self.domain.name:
                return self.domain.name
            else:
                return f"application created by {self.creator}"
        except Exception:
            return ""

    @classmethod
    def create_from_da(cls, domain_application):
        """Takes in a DomainApplication dict and converts it into DomainInformation"""
        da_dict = domain_application.to_dict()
        # remove the id so one can be assinged on creation
        da_id = da_dict.pop("id")
        # check if we have a record that corresponds with the domain
        # application, if so short circuit the create
        domain_info = cls.objects.filter(domain_application__id=da_id).first()
        if domain_info:
            return domain_info
        # the following information below is not needed in the domain information:
        da_dict.pop("status")
        da_dict.pop("current_websites")
        da_dict.pop("investigator")
        da_dict.pop("alternative_domains")
        # use the requested_domain to create information for this domain
        da_dict["domain"] = da_dict.pop("requested_domain")
        other_contacts = da_dict.pop("other_contacts")
        domain_info = cls(**da_dict)
        domain_info.domain_application = domain_application
        # Save so the object now have PK
        # (needed to process the manytomany below before, first)
        domain_info.save()

        # Process the remaining "many to many" stuff
        domain_info.other_contacts.add(*other_contacts)
        domain_info.save()
        return domain_info

    class Meta:
        verbose_name_plural = "Domain Information"
