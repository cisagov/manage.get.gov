from __future__ import annotations
from django.db import transaction

from registrar.models.utility.domain_helper import DomainHelper
from registrar.models.utility.generic_helper import CreateOrUpdateOrganizationTypeHelper
from .domain_request import DomainRequest
from .utility.time_stamped_model import TimeStampedModel

import logging

from django.db import models


logger = logging.getLogger(__name__)


class DomainInformation(TimeStampedModel):
    """A registrant's domain information for that domain, exported from
    DomainRequest. We use these field from DomainRequest with few exceptions
    which are 'removed' via pop at the bottom of this file. Most of design for domain
    management's user information are based on domain_request, but we cannot change
    the domain request once approved, so copying them that way we can make changes
    after its approved. Most fields here are copied from DomainRequest."""

    StateTerritoryChoices = DomainRequest.StateTerritoryChoices

    # use the short names in Django admin
    OrganizationChoices = DomainRequest.OrganizationChoices

    BranchChoices = DomainRequest.BranchChoices

    AGENCY_CHOICES = DomainRequest.AGENCY_CHOICES

    # This is the domain request user who created this domain request. The contact
    # information that they gave is in the `submitter` field
    creator = models.ForeignKey(
        "registrar.User",
        on_delete=models.PROTECT,
        related_name="information_created",
    )

    domain_request = models.OneToOneField(
        "registrar.DomainRequest",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="DomainRequest_info",
        help_text="Associated domain request",
        unique=True,
    )

    # ##### data fields from the initial form #####
    generic_org_type = models.CharField(
        max_length=255,
        choices=OrganizationChoices.choices,
        null=True,
        blank=True,
        help_text="Type of organization",
    )

    # TODO - Ticket #1911: stub this data from DomainRequest
    is_election_board = models.BooleanField(
        null=True,
        blank=True,
        verbose_name="Election office",
        help_text="Is your organization an election office?",
    )

    # TODO - Ticket #1911: stub this data from DomainRequest
    organization_type = models.CharField(
        max_length=255,
        choices=DomainRequest.OrgChoicesElectionOffice.choices,
        null=True,
        blank=True,
        help_text="Type of organization - Election office",
    )

    federally_recognized_tribe = models.BooleanField(
        null=True,
        help_text="Is the tribe federally recognized",
    )

    state_recognized_tribe = models.BooleanField(
        null=True,
        help_text="Is the tribe recognized by a state",
    )

    tribe_name = models.CharField(
        null=True,
        blank=True,
        help_text="Name of tribe",
    )

    federal_agency = models.CharField(
        choices=AGENCY_CHOICES,
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
        verbose_name="Election office",
        help_text="Is your organization an election office?",
    )

    organization_name = models.CharField(
        null=True,
        blank=True,
        help_text="Organization name",
        db_index=True,
    )
    address_line1 = models.CharField(
        null=True,
        blank=True,
        help_text="Street address",
        verbose_name="Address line 1",
    )
    address_line2 = models.CharField(
        null=True,
        blank=True,
        help_text="Street address line 2 (optional)",
        verbose_name="Address line 2",
    )
    city = models.CharField(
        null=True,
        blank=True,
        help_text="City",
    )
    state_territory = models.CharField(
        max_length=2,
        choices=StateTerritoryChoices.choices,
        null=True,
        blank=True,
        verbose_name="State / territory",
        help_text="State, territory, or military post",
    )
    zipcode = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text="Zip code",
        verbose_name="Zip code",
        db_index=True,
    )
    urbanization = models.CharField(
        null=True,
        blank=True,
        help_text="Urbanization (required for Puerto Rico only)",
        verbose_name="Urbanization",
    )

    about_your_organization = models.TextField(
        null=True,
        blank=True,
        help_text="Information about your organization",
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
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        # Access this information via Domain as "domain.domain_info"
        related_name="domain_info",
        verbose_name="Domain request",
        help_text="Domain to which this information belongs",
    )

    # This is the contact information provided by the domain requestor. The
    # user who created the domain request is in the `creator` field.
    submitter = models.ForeignKey(
        "registrar.Contact",
        null=True,
        blank=True,
        related_name="submitted_domain_requests_information",
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
        related_name="contact_domain_requests_information",
        verbose_name="Other employees",
    )

    no_other_contacts_rationale = models.TextField(
        null=True,
        blank=True,
        help_text="Reason for listing no additional contacts",
    )

    anything_else = models.TextField(
        null=True,
        blank=True,
        help_text="Anything else?",
    )

    is_policy_acknowledged = models.BooleanField(
        null=True,
        blank=True,
        help_text="Acknowledged .gov acceptable use policy",
    )

    notes = models.TextField(
        null=True,
        blank=True,
        help_text="Notes about the request",
    )

    def __str__(self):
        try:
            if self.domain and self.domain.name:
                return self.domain.name
            else:
                return f"domain info set up and created by {self.creator}"
        except Exception:
            return ""

    def save(self, *args, **kwargs):
        """Save override for custom properties"""

        # Define mappings between generic org and election org.
        # These have to be defined here, as you'd get a cyclical import error
        # otherwise.

        # For any given organization type, return the "_election" variant.
        # For example: STATE_OR_TERRITORY => STATE_OR_TERRITORY_ELECTION
        generic_org_map = DomainRequest.OrgChoicesElectionOffice.get_org_generic_to_org_election()

        # For any given "_election" variant, return the base org type.
        # For example: STATE_OR_TERRITORY_ELECTION => STATE_OR_TERRITORY
        election_org_map = DomainRequest.OrgChoicesElectionOffice.get_org_election_to_org_generic()

        # Manages the "organization_type" variable and keeps in sync with
        # "is_election_office" and "generic_organization_type"
        org_type_helper = CreateOrUpdateOrganizationTypeHelper(
            sender=self.__class__,
            instance=self,
            generic_org_to_org_map=generic_org_map,
            election_org_to_generic_org_map=election_org_map,
        )

        # Actually updates the organization_type field
        org_type_helper.create_or_update_organization_type()
        super().save(*args, **kwargs)

    @classmethod
    def create_from_da(cls, domain_request: DomainRequest, domain=None):
        """Takes in a DomainRequest and converts it into DomainInformation"""

        # Throw an error if we get None - we can't create something from nothing
        if domain_request is None:
            raise ValueError("The provided DomainRequest is None")

        # Throw an error if the da doesn't have an id
        if not hasattr(domain_request, "id"):
            raise ValueError("The provided DomainRequest has no id")

        # check if we have a record that corresponds with the domain
        # domain_request, if so short circuit the create
        existing_domain_info = cls.objects.filter(domain_request__id=domain_request.id).first()
        if existing_domain_info:
            return existing_domain_info

        # Get the fields that exist on both DomainRequest and DomainInformation
        common_fields = DomainHelper.get_common_fields(DomainRequest, DomainInformation)

        # Get a list of all many_to_many relations on DomainInformation (needs to be saved differently)
        info_many_to_many_fields = DomainInformation._get_many_to_many_fields()

        # Create a dictionary with only the common fields, and create a DomainInformation from it
        da_dict = {}
        da_many_to_many_dict = {}
        for field in common_fields:
            # If the field isn't many_to_many, populate the da_dict.
            # If it is, populate da_many_to_many_dict as we need to save this later.
            if hasattr(domain_request, field):
                if field not in info_many_to_many_fields:
                    da_dict[field] = getattr(domain_request, field)
                else:
                    da_many_to_many_dict[field] = getattr(domain_request, field).all()

        # This will not happen in normal code flow, but having some redundancy doesn't hurt.
        # da_dict should not have "id" under any circumstances.
        # If it does have it, then this indicates that common_fields is overzealous in the data
        # that it is returning. Try looking in DomainHelper.get_common_fields.
        if "id" in da_dict:
            logger.warning("create_from_da() -> Found attribute 'id' when trying to create")
            da_dict.pop("id", None)

        # Create a placeholder DomainInformation object
        domain_info = DomainInformation(**da_dict)

        # Add the domain_request and domain fields
        domain_info.domain_request = domain_request
        if domain:
            domain_info.domain = domain

        # Save the instance and set the many-to-many fields.
        # Lumped under .atomic to ensure we don't make redundant DB calls.
        # This bundles them all together, and then saves it in a single call.
        with transaction.atomic():
            domain_info.save()
            for field, value in da_many_to_many_dict.items():
                getattr(domain_info, field).set(value)

        return domain_info

    @staticmethod
    def _get_many_to_many_fields():
        """Returns a set of each field.name that has the many to many relation"""
        return {field.name for field in DomainInformation._meta.many_to_many}  # type: ignore

    class Meta:
        verbose_name_plural = "Domain information"
