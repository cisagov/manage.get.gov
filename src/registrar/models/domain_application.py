from __future__ import annotations
from typing import Union

import logging

from django.apps import apps
from django.db import models
from django_fsm import FSMField, transition  # type: ignore

from .utility.time_stamped_model import TimeStampedModel
from ..utility.email import send_templated_email, EmailSendingError
from itertools import chain

logger = logging.getLogger(__name__)


class DomainApplication(TimeStampedModel):

    """A registrant's application for a new domain."""

    # #### Constants for choice fields ####
    STARTED = "started"
    SUBMITTED = "submitted"
    IN_REVIEW = "in review"
    ACTION_NEEDED = "action needed"
    APPROVED = "approved"
    WITHDRAWN = "withdrawn"
    REJECTED = "rejected"
    INELIGIBLE = "ineligible"
    STATUS_CHOICES = [
        (STARTED, STARTED),
        (SUBMITTED, SUBMITTED),
        (IN_REVIEW, IN_REVIEW),
        (ACTION_NEEDED, ACTION_NEEDED),
        (APPROVED, APPROVED),
        (WITHDRAWN, WITHDRAWN),
        (REJECTED, REJECTED),
        (INELIGIBLE, INELIGIBLE),
    ]

    class StateTerritoryChoices(models.TextChoices):
        ALABAMA = "AL", "Alabama (AL)"
        ALASKA = "AK", "Alaska (AK)"
        AMERICAN_SAMOA = "AS", "American Samoa (AS)"
        ARIZONA = "AZ", "Arizona (AZ)"
        ARKANSAS = "AR", "Arkansas (AR)"
        CALIFORNIA = "CA", "California (CA)"
        COLORADO = "CO", "Colorado (CO)"
        CONNECTICUT = "CT", "Connecticut (CT)"
        DELAWARE = "DE", "Delaware (DE)"
        DISTRICT_OF_COLUMBIA = "DC", "District of Columbia (DC)"
        FLORIDA = "FL", "Florida (FL)"
        GEORGIA = "GA", "Georgia (GA)"
        GUAM = "GU", "Guam (GU)"
        HAWAII = "HI", "Hawaii (HI)"
        IDAHO = "ID", "Idaho (ID)"
        ILLINOIS = "IL", "Illinois (IL)"
        INDIANA = "IN", "Indiana (IN)"
        IOWA = "IA", "Iowa (IA)"
        KANSAS = "KS", "Kansas (KS)"
        KENTUCKY = "KY", "Kentucky (KY)"
        LOUISIANA = "LA", "Louisiana (LA)"
        MAINE = "ME", "Maine (ME)"
        MARYLAND = "MD", "Maryland (MD)"
        MASSACHUSETTS = "MA", "Massachusetts (MA)"
        MICHIGAN = "MI", "Michigan (MI)"
        MINNESOTA = "MN", "Minnesota (MN)"
        MISSISSIPPI = "MS", "Mississippi (MS)"
        MISSOURI = "MO", "Missouri (MO)"
        MONTANA = "MT", "Montana (MT)"
        NEBRASKA = "NE", "Nebraska (NE)"
        NEVADA = "NV", "Nevada (NV)"
        NEW_HAMPSHIRE = "NH", "New Hampshire (NH)"
        NEW_JERSEY = "NJ", "New Jersey (NJ)"
        NEW_MEXICO = "NM", "New Mexico (NM)"
        NEW_YORK = "NY", "New York (NY)"
        NORTH_CAROLINA = "NC", "North Carolina (NC)"
        NORTH_DAKOTA = "ND", "North Dakota (ND)"
        NORTHERN_MARIANA_ISLANDS = "MP", "Northern Mariana Islands (MP)"
        OHIO = "OH", "Ohio (OH)"
        OKLAHOMA = "OK", "Oklahoma (OK)"
        OREGON = "OR", "Oregon (OR)"
        PENNSYLVANIA = "PA", "Pennsylvania (PA)"
        PUERTO_RICO = "PR", "Puerto Rico (PR)"
        RHODE_ISLAND = "RI", "Rhode Island (RI)"
        SOUTH_CAROLINA = "SC", "South Carolina (SC)"
        SOUTH_DAKOTA = "SD", "South Dakota (SD)"
        TENNESSEE = "TN", "Tennessee (TN)"
        TEXAS = "TX", "Texas (TX)"
        UNITED_STATES_MINOR_OUTLYING_ISLANDS = (
            "UM",
            "United States Minor Outlying Islands (UM)",
        )
        UTAH = "UT", "Utah (UT)"
        VERMONT = "VT", "Vermont (VT)"
        VIRGIN_ISLANDS = "VI", "Virgin Islands (VI)"
        VIRGINIA = "VA", "Virginia (VA)"
        WASHINGTON = "WA", "Washington (WA)"
        WEST_VIRGINIA = "WV", "West Virginia (WV)"
        WISCONSIN = "WI", "Wisconsin (WI)"
        WYOMING = "WY", "Wyoming (WY)"
        ARMED_FORCES_AA = "AA", "Armed Forces Americas (AA)"
        ARMED_FORCES_AE = "AE", "Armed Forces Africa, Canada, Europe, Middle East (AE)"
        ARMED_FORCES_AP = "AP", "Armed Forces Pacific (AP)"

    class OrganizationChoices(models.TextChoices):
        FEDERAL = (
            "federal",
            "Federal: an agency of the U.S. government's executive, legislative, "
            "or judicial branches",
        )
        INTERSTATE = "interstate", "Interstate: an organization of two or more states"
        STATE_OR_TERRITORY = "state_or_territory", (
            "State or territory: one of the 50 U.S. states, the District of "
            "Columbia, American Samoa, Guam, Northern Mariana Islands, "
            "Puerto Rico, or the U.S. Virgin Islands"
        )
        TRIBAL = "tribal", (
            "Tribal: a tribal government recognized by the federal or "
            "a state government"
        )
        COUNTY = "county", "County: a county, parish, or borough"
        CITY = "city", "City: a city, town, township, village, etc."
        SPECIAL_DISTRICT = "special_district", (
            "Special district: an independent organization within a single state"
        )
        SCHOOL_DISTRICT = "school_district", (
            "School district: a school district that is not part of a local government"
        )

    class BranchChoices(models.TextChoices):
        EXECUTIVE = "executive", "Executive"
        JUDICIAL = "judicial", "Judicial"
        LEGISLATIVE = "legislative", "Legislative"

    AGENCIES = [
        "Administrative Conference of the United States",
        "Advisory Council on Historic Preservation",
        "American Battle Monuments Commission",
        "Appalachian Regional Commission",
        (
            "Appraisal Subcommittee of the Federal Financial "
            "Institutions Examination Council"
        ),
        "Armed Forces Retirement Home",
        "Barry Goldwater Scholarship and Excellence in Education Program",
        "Central Intelligence Agency",
        "Christopher Columbus Fellowship Foundation",
        "Commission for the Preservation of America's Heritage Abroad",
        "Commission of Fine Arts",
        "Committee for Purchase From People Who Are Blind or Severely Disabled",
        "Commodity Futures Trading Commission",
        "Consumer Financial Protection Bureau",
        "Consumer Product Safety Commission",
        "Corporation for National and Community Service",
        "Council of Inspectors General on Integrity and Efficiency",
        "DC Court Services and Offender Supervision Agency",
        "DC Pre-trial Services",
        "Defense Nuclear Facilities Safety Board",
        "Delta Regional Authority",
        "Denali Commission",
        "Department of Agriculture",
        "Department of Commerce",
        "Department of Defense",
        "Department of Education",
        "Department of Energy",
        "Department of Health and Human Services",
        "Department of Homeland Security",
        "Department of Housing and Urban Development",
        "Department of Justice",
        "Department of Labor",
        "Department of State",
        "Department of the Interior",
        "Department of the Treasury",
        "Department of Transportation",
        "Department of Veterans Affairs",
        "Director of National Intelligence",
        "Dwight D. Eisenhower Memorial Commission",
        "Election Assistance Commission",
        "Environmental Protection Agency",
        "Equal Employment Opportunity Commission",
        "Export-Import Bank of the United States",
        "Farm Credit Administration",
        "Farm Credit System Insurance Corporation",
        "Federal Communications Commission",
        "Federal Deposit Insurance Corporation",
        "Federal Election Commission",
        "Federal Financial Institutions Examination Council",
        "Federal Housing Finance Agency",
        "Federal Judiciary",
        "Federal Labor Relations Authority",
        "Federal Maritime Commission",
        "Federal Mediation and Conciliation Service",
        "Federal Mine Safety and Health Review Commission",
        "Federal Reserve System",
        "Federal Trade Commission",
        "General Services Administration",
        "Gulf Coast Ecosystem Restoration Council",
        "Harry S Truman Scholarship Foundation",
        "Institute of Peace",
        "Inter-American Foundation",
        "International Boundary and Water Commission: United States and Mexico",
        "International Boundary Commission:  United States and Canada",
        "International Joint Commission:  United States and Canada",
        "James Madison Memorial Fellowship Foundation",
        "Japan-United States Friendship Commission",
        "John F. Kennedy Center for the Performing Arts",
        "Legal Services Corporation",
        "Legislative Branch",
        "Marine Mammal Commission",
        "Medicare Payment Advisory Commission",
        "Merit Systems Protection Board",
        "Millennium Challenge Corporation",
        "National Aeronautics and Space Administration",
        "National Archives and Records Administration",
        "National Capital Planning Commission",
        "National Council on Disability",
        "National Credit Union Administration",
        "National Foundation on the Arts and the Humanities",
        "National Gallery of Art",
        "National Labor Relations Board",
        "National Mediation Board",
        "National Science Foundation",
        "National Transportation Safety Board",
        "Northern Border Regional Commission",
        "Nuclear Regulatory Commission",
        "Nuclear Safety Oversight Committee",
        "Nuclear Waste Technical Review Board",
        "Occupational Safety and Health Review Commission",
        "Office of Compliance",
        "Office of Government Ethics",
        "Office of Navajo and Hopi Indian Relocation",
        "Office of Personnel Management",
        "Overseas Private Investment Corporation",
        "Peace Corps",
        "Pension Benefit Guaranty Corporation",
        "Postal Regulatory Commission",
        "Privacy and Civil Liberties Oversight Board",
        "Public Defender Service for the District of Columbia",
        "Railroad Retirement Board",
        "Securities and Exchange Commission",
        "Selective Service System",
        "Small Business Administration",
        "Smithsonian Institution",
        "Social Security Administration",
        "State Justice Institute",
        "State, Local, and Tribal Government",
        "Stennis Center for Public Service",
        "Surface Transportation Board",
        "Tennessee Valley Authority",
        "The Executive Office of the President",
        "U.S. Access Board",
        "U.S. Agency for Global Media",
        "U.S. Agency for International Development",
        "U.S. Chemical Safety Board",
        "U.S. China Economic and Security Review Commission",
        "U.S. Commission on Civil Rights",
        "U.S. Commission on International Religious Freedom",
        "U.S. Interagency Council on Homelessness",
        "U.S. International Trade Commission",
        "U.S. Office of Special Counsel",
        "U.S. Postal Service",
        "U.S. Trade and Development Agency",
        "Udall Foundation",
        "United States African Development Foundation",
        "United States Arctic Research Commission",
        "United States Holocaust Memorial Museum",
        "Utah Reclamation Mitigation and Conservation Commission",
        "Vietnam Education Foundation",
        "Woodrow Wilson International Center for Scholars",
        "World War I Centennial Commission",
    ]
    AGENCY_CHOICES = [(v, v) for v in AGENCIES]

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
        help_text="Type of organization",
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
    address_line2 = models.TextField(
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
        help_text="More information about your organization",
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

    approved_domain = models.OneToOneField(
        "Domain",
        null=True,
        blank=True,
        help_text="The approved domain",
        related_name="domain_application",
        on_delete=models.SET_NULL,
    )

    requested_domain = models.OneToOneField(
        "DraftDomain",
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
        help_text="Purpose of your domain",
    )

    other_contacts = models.ManyToManyField(
        "registrar.Contact",
        blank=True,
        related_name="contact_applications",
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

    def __str__(self):
        try:
            if self.requested_domain and self.requested_domain.name:
                return self.requested_domain.name
            else:
                return f"{self.status} application created by {self.creator}"
        except Exception:
            return ""

    def domain_is_not_active(self):
        if self.approved_domain:
            return not self.approved_domain.is_active()
        return True

    def _send_status_update_email(
        self, new_status, email_template, email_template_subject
    ):
        """Send a atatus update email to the submitter.

        The email goes to the email address that the submitter gave as their
        contact information. If there is not submitter information, then do
        nothing.
        """

        if self.submitter is None or self.submitter.email is None:
            logger.warning(
                f"Cannot send {new_status} email, no submitter email address."
            )
            return
        try:
            send_templated_email(
                email_template,
                email_template_subject,
                self.submitter.email,
                context={"application": self},
            )
            logger.info(f"The {new_status} email sent to: {self.submitter.email}")
        except EmailSendingError:
            logger.warning("Failed to send confirmation email", exc_info=True)

    @transition(
        field="status", source=[STARTED, ACTION_NEEDED, WITHDRAWN], target=SUBMITTED
    )
    def submit(self):
        """Submit an application that is started.

        As a side effect, an email notification is sent."""

        # check our conditions here inside the `submit` method so that we
        # can raise more informative exceptions

        # requested_domain could be None here
        if not hasattr(self, "requested_domain"):
            raise ValueError("Requested domain is missing.")

        if self.requested_domain is None:
            raise ValueError("Requested domain is missing.")

        DraftDomain = apps.get_model("registrar.DraftDomain")
        if not DraftDomain.string_could_be_domain(self.requested_domain.name):
            raise ValueError("Requested domain is not a valid domain name.")

        self._send_status_update_email(
            "submission confirmation",
            "emails/submission_confirmation.txt",
            "emails/submission_confirmation_subject.txt",
        )

    @transition(field="status", source=SUBMITTED, target=IN_REVIEW)
    def in_review(self):
        """Investigate an application that has been submitted.

        As a side effect, an email notification is sent."""

        self._send_status_update_email(
            "application in review",
            "emails/status_change_in_review.txt",
            "emails/status_change_in_review_subject.txt",
        )

    @transition(field="status", source=[IN_REVIEW, REJECTED], target=ACTION_NEEDED)
    def action_needed(self):
        """Send back an application that is under investigation or rejected.

        As a side effect, an email notification is sent."""

        self._send_status_update_email(
            "action needed",
            "emails/status_change_action_needed.txt",
            "emails/status_change_action_needed_subject.txt",
        )

    @transition(
        field="status",
        source=[SUBMITTED, IN_REVIEW, REJECTED, INELIGIBLE],
        target=APPROVED,
    )
    def approve(self):
        """Approve an application that has been submitted.

        This has substantial side-effects because it creates another database
        object for the approved Domain and makes the user who created the
        application into an admin on that domain. It also triggers an email
        notification."""

        # create the domain
        Domain = apps.get_model("registrar.Domain")
        if Domain.objects.filter(name=self.requested_domain.name).exists():
            raise ValueError("Cannot approve. Requested domain is already in use.")
        created_domain = Domain.objects.create(name=self.requested_domain.name)
        self.approved_domain = created_domain

        # copy the information from domainapplication into domaininformation
        DomainInformation = apps.get_model("registrar.DomainInformation")
        DomainInformation.create_from_da(self, domain=created_domain)

        # create the permission for the user
        UserDomainRole = apps.get_model("registrar.UserDomainRole")
        UserDomainRole.objects.get_or_create(
            user=self.creator, domain=created_domain, role=UserDomainRole.Roles.ADMIN
        )

        self._send_status_update_email(
            "application approved",
            "emails/status_change_approved.txt",
            "emails/status_change_approved_subject.txt",
        )

    @transition(field="status", source=[SUBMITTED, IN_REVIEW], target=WITHDRAWN)
    def withdraw(self):
        """Withdraw an application that has been submitted."""
        self._send_status_update_email(
            "withdraw",
            "emails/domain_request_withdrawn.txt",
            "emails/domain_request_withdrawn_subject.txt",
        )

    @transition(
        field="status",
        source=[IN_REVIEW, APPROVED],
        target=REJECTED,
        conditions=[domain_is_not_active],
    )
    def reject(self):
        """Reject an application that has been submitted.

        As a side effect this will delete the domain and domain_information
        (will cascade), and send an email notification"""

        if self.status == self.APPROVED:
            self.approved_domain.delete_request()
            self.approved_domain.delete()
            self.approved_domain = None

        self._send_status_update_email(
            "action needed",
            "emails/status_change_rejected.txt",
            "emails/status_change_rejected_subject.txt",
        )

    @transition(
        field="status",
        source=[IN_REVIEW, APPROVED],
        target=INELIGIBLE,
        conditions=[domain_is_not_active],
    )
    def reject_with_prejudice(self):
        """The applicant is a bad actor, reject with prejudice.

        No email As a side effect, but we block the applicant from editing
        any existing domains/applications and from submitting new aplications.
        We do this by setting an ineligible status on the user, which the
        permissions classes test against. This will also delete the domain
        and domain_information (will cascade)"""

        if self.status == self.APPROVED:
            self.approved_domain.delete_request()
            self.approved_domain.delete()
            self.approved_domain = None

        self.creator.restrict_user()

    # ## Form policies ###
    #
    # These methods control what questions need to be answered by applicants
    # during the application flow. They are policies about the application so
    # they appear here.

    def show_organization_federal(self) -> bool:
        """Show this step if the answer to the first question was "federal"."""
        user_choice = self.organization_type
        return user_choice == DomainApplication.OrganizationChoices.FEDERAL

    def show_tribal_government(self) -> bool:
        """Show this step if the answer to the first question was "tribal"."""
        user_choice = self.organization_type
        return user_choice == DomainApplication.OrganizationChoices.TRIBAL

    def show_organization_election(self) -> bool:
        """Show this step if the answer to the first question implies it.

        This shows for answers that aren't "Federal" or "Interstate".
        This also doesnt show if user selected "School District" as well (#524)
        """
        user_choice = self.organization_type
        excluded = [
            DomainApplication.OrganizationChoices.FEDERAL,
            DomainApplication.OrganizationChoices.INTERSTATE,
            DomainApplication.OrganizationChoices.SCHOOL_DISTRICT,
        ]
        return bool(user_choice and user_choice not in excluded)

    def show_type_of_work(self) -> bool:
        """Show this step if this is a special district or interstate."""
        user_choice = self.organization_type
        return user_choice in [
            DomainApplication.OrganizationChoices.SPECIAL_DISTRICT,
            DomainApplication.OrganizationChoices.INTERSTATE,
        ]

    def show_no_other_contacts_rationale(self) -> bool:
        """Show this step if the other contacts are blank."""
        return not self.other_contacts.exists()

    def is_federal(self) -> Union[bool, None]:
        """Is this application for a federal agency?

        organization_type can be both null and blank,
        """
        if not self.organization_type:
            # organization_type is either blank or None, can't answer
            return None
        if self.organization_type == DomainApplication.OrganizationChoices.FEDERAL:
            return True
        return False

    def to_dict(self):
        """This is to process to_dict for Domain Information, making it friendly
        to "copy" it

        More information can be found at this- (This used #5)
        https://stackoverflow.com/questions/21925671/convert-django-model-object-to-dict-with-all-of-the-fields-intact/29088221#29088221
        """  # noqa 590
        opts = self._meta
        data = {}
        for field in chain(opts.concrete_fields, opts.private_fields):
            if field.get_internal_type() in ("ForeignKey", "OneToOneField"):
                # get the related instance of the FK value
                fk_id = field.value_from_object(self)
                if fk_id:
                    data[field.name] = field.related_model.objects.get(id=fk_id)
                else:
                    data[field.name] = None
            else:
                data[field.name] = field.value_from_object(self)
        for field in opts.many_to_many:
            data[field.name] = field.value_from_object(self)
        return data
