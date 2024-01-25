from __future__ import annotations
from typing import Union

import logging

from django.apps import apps
from django.db import models
from django_fsm import FSMField, transition  # type: ignore
from django.utils import timezone
from registrar.models.domain import Domain

from .utility.time_stamped_model import TimeStampedModel
from ..utility.email import send_templated_email, EmailSendingError
from itertools import chain

logger = logging.getLogger(__name__)


class DomainApplication(TimeStampedModel):

    """A registrant's application for a new domain."""

    # Constants for choice fields
    class ApplicationStatus(models.TextChoices):
        STARTED = "started", "Started"
        SUBMITTED = "submitted", "Submitted"
        IN_REVIEW = "in review", "In review"
        ACTION_NEEDED = "action needed", "Action needed"
        APPROVED = "approved", "Approved"
        WITHDRAWN = "withdrawn", "Withdrawn"
        REJECTED = "rejected", "Rejected"
        INELIGIBLE = "ineligible", "Ineligible"

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

        """
        Primary organization choices:
        For use in django admin
        Keys need to match OrganizationChoicesVerbose
        """

        FEDERAL = "federal", "Federal"
        INTERSTATE = "interstate", "Interstate"
        STATE_OR_TERRITORY = "state_or_territory", "State or territory"
        TRIBAL = "tribal", "Tribal"
        COUNTY = "county", "County"
        CITY = "city", "City"
        SPECIAL_DISTRICT = "special_district", "Special district"
        SCHOOL_DISTRICT = "school_district", "School district"

    class OrganizationChoicesVerbose(models.TextChoices):

        """
        Secondary organization choices
        For use in the application form and on the templates
        Keys need to match OrganizationChoices
        """

        FEDERAL = (
            "federal",
            "Federal: an agency of the U.S. government’s legislative, executive, or judicial branches",
        )
        INTERSTATE = "interstate", "Interstate: an organization of two or more states"
        STATE_OR_TERRITORY = (
            "state_or_territory",
            "State or territory: one of the 50 U.S. states, the District of Columbia, "
            "American Samoa, Guam, Northern Mariana Islands, Puerto Rico, or the U.S. "
            "Virgin Islands",
        )
        TRIBAL = (
            "tribal",
            "Tribal: a tribal government recognized by the federal or a state government",
        )
        COUNTY = "county", "County: a county, parish, or borough"
        CITY = "city", "City: a city, town, township, village, etc."
        SPECIAL_DISTRICT = (
            "special_district",
            "Special district: an independent government that delivers specialized, essential services",
        )
        SCHOOL_DISTRICT = (
            "school_district",
            "School district: a school district that is not part of a local government",
        )

    class BranchChoices(models.TextChoices):
        EXECUTIVE = "executive", "Executive"
        JUDICIAL = "judicial", "Judicial"
        LEGISLATIVE = "legislative", "Legislative"

    AGENCIES = [
        "Administrative Conference of the United States",
        "Advisory Council on Historic Preservation",
        "American Battle Monuments Commission",
        "AMTRAK",
        "Appalachian Regional Commission",
        ("Appraisal Subcommittee of the Federal Financial " "Institutions Examination Council"),
        "Appraisal Subcommittee",
        "Architect of the Capitol",
        "Armed Forces Retirement Home",
        "Barry Goldwater Scholarship and Excellence in Education Foundation",
        "Barry Goldwater Scholarship and Excellence in Education Program",
        "Central Intelligence Agency",
        "Chemical Safety Board",
        "Christopher Columbus Fellowship Foundation",
        "Civil Rights Cold Case Records Review Board",
        "Commission for the Preservation of America's Heritage Abroad",
        "Commission of Fine Arts",
        "Committee for Purchase From People Who Are Blind or Severely Disabled",
        "Commodity Futures Trading Commission",
        "Congressional Budget Office",
        "Consumer Financial Protection Bureau",
        "Consumer Product Safety Commission",
        "Corporation for National & Community Service",
        "Corporation for National and Community Service",
        "Council of Inspectors General on Integrity and Efficiency",
        "Court Services and Offender Supervision",
        "Cyberspace Solarium Commission",
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
        "Executive Office of the President",
        "Export-Import Bank of the United States",
        "Export/Import Bank of the U.S.",
        "Farm Credit Administration",
        "Farm Credit System Insurance Corporation",
        "Federal Communications Commission",
        "Federal Deposit Insurance Corporation",
        "Federal Election Commission",
        "Federal Energy Regulatory Commission",
        "Federal Financial Institutions Examination Council",
        "Federal Housing Finance Agency",
        "Federal Judiciary",
        "Federal Labor Relations Authority",
        "Federal Maritime Commission",
        "Federal Mediation and Conciliation Service",
        "Federal Mine Safety and Health Review Commission",
        "Federal Permitting Improvement Steering Council",
        "Federal Reserve Board of Governors",
        "Federal Reserve System",
        "Federal Trade Commission",
        "General Services Administration",
        "gov Administration",
        "Government Accountability Office",
        "Government Publishing Office",
        "Gulf Coast Ecosystem Restoration Council",
        "Harry S Truman Scholarship Foundation",
        "Harry S. Truman Scholarship Foundation",
        "Institute of Museum and Library Services",
        "Institute of Peace",
        "Inter-American Foundation",
        "International Boundary and Water Commission: United States and Mexico",
        "International Boundary Commission: United States and Canada",
        "International Joint Commission: United States and Canada",
        "James Madison Memorial Fellowship Foundation",
        "Japan-United States Friendship Commission",
        "Japan-US Friendship Commission",
        "John F. Kennedy Center for Performing Arts",
        "John F. Kennedy Center for the Performing Arts",
        "Legal Services Corporation",
        "Legislative Branch",
        "Library of Congress",
        "Marine Mammal Commission",
        "Medicaid and CHIP Payment and Access Commission",
        "Medical Payment Advisory Commission",
        "Medicare Payment Advisory Commission",
        "Merit Systems Protection Board",
        "Millennium Challenge Corporation",
        "Morris K. Udall and Stewart L. Udall Foundation",
        "National Aeronautics and Space Administration",
        "National Archives and Records Administration",
        "National Capital Planning Commission",
        "National Council on Disability",
        "National Credit Union Administration",
        "National Endowment for the Arts",
        "National Endowment for the Humanities",
        "National Foundation on the Arts and the Humanities",
        "National Gallery of Art",
        "National Indian Gaming Commission",
        "National Labor Relations Board",
        "National Mediation Board",
        "National Science Foundation",
        "National Security Commission on Artificial Intelligence",
        "National Transportation Safety Board",
        "Networking Information Technology Research and Development",
        "Non-Federal Agency",
        "Northern Border Regional Commission",
        "Nuclear Regulatory Commission",
        "Nuclear Safety Oversight Committee",
        "Nuclear Waste Technical Review Board",
        "Occupational Safety & Health Review Commission",
        "Occupational Safety and Health Review Commission",
        "Office of Compliance",
        "Office of Congressional Workplace Rights",
        "Office of Government Ethics",
        "Office of Navajo and Hopi Indian Relocation",
        "Office of Personnel Management",
        "Open World Leadership Center",
        "Overseas Private Investment Corporation",
        "Peace Corps",
        "Pension Benefit Guaranty Corporation",
        "Postal Regulatory Commission",
        "Presidio Trust",
        "Privacy and Civil Liberties Oversight Board",
        "Public Buildings Reform Board",
        "Public Defender Service for the District of Columbia",
        "Railroad Retirement Board",
        "Securities and Exchange Commission",
        "Selective Service System",
        "Small Business Administration",
        "Smithsonian Institution",
        "Social Security Administration",
        "Social Security Advisory Board",
        "Southeast Crescent Regional Commission",
        "Southwest Border Regional Commission",
        "State Justice Institute",
        "State, Local, and Tribal Government",
        "Stennis Center for Public Service",
        "Surface Transportation Board",
        "Tennessee Valley Authority",
        "The Executive Office of the President",
        "The Intelligence Community",
        "The Legislative Branch",
        "The Supreme Court",
        "The United States World War One Centennial Commission",
        "U.S. Access Board",
        "U.S. Agency for Global Media",
        "U.S. Agency for International Development",
        "U.S. Capitol Police",
        "U.S. Chemical Safety Board",
        "U.S. China Economic and Security Review Commission",
        "U.S. Commission for the Preservation of Americas Heritage Abroad",
        "U.S. Commission of Fine Arts",
        "U.S. Commission on Civil Rights",
        "U.S. Commission on International Religious Freedom",
        "U.S. Courts",
        "U.S. Department of Agriculture",
        "U.S. Interagency Council on Homelessness",
        "U.S. International Trade Commission",
        "U.S. Nuclear Waste Technical Review Board",
        "U.S. Office of Special Counsel",
        "U.S. Peace Corps",
        "U.S. Postal Service",
        "U.S. Semiquincentennial Commission",
        "U.S. Trade and Development Agency",
        "U.S.-China Economic and Security Review Commission",
        "Udall Foundation",
        "United States AbilityOne",
        "United States Access Board",
        "United States African Development Foundation",
        "United States Agency for Global Media",
        "United States Arctic Research Commission",
        "United States Global Change Research Program",
        "United States Holocaust Memorial Museum",
        "United States Institute of Peace",
        "United States Interagency Council on Homelessness",
        "United States International Development Finance Corporation",
        "United States International Trade Commission",
        "United States Postal Service",
        "United States Senate",
        "United States Trade and Development Agency",
        "Utah Reclamation Mitigation and Conservation Commission",
        "Vietnam Education Foundation",
        "Western Hemisphere Drug Policy Commission",
        "Woodrow Wilson International Center for Scholars",
        "World War I Centennial Commission",
    ]
    AGENCY_CHOICES = [(v, v) for v in AGENCIES]

    # #### Internal fields about the application #####
    status = FSMField(
        choices=ApplicationStatus.choices,  # possible states as an array of constants
        default=ApplicationStatus.STARTED,  # sensible default
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
        # use the short names in Django admin
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
        verbose_name="Address line 1",
    )
    address_line2 = models.TextField(
        null=True,
        blank=True,
        help_text="Street address line 2 (optional)",
        verbose_name="Address line 2",
    )
    city = models.TextField(
        null=True,
        blank=True,
        help_text="City",
    )
    state_territory = models.CharField(
        max_length=2,
        choices=StateTerritoryChoices.choices,
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
        help_text="Urbanization (required for Puerto Rico only)",
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
        related_name="authorizing_official",
        on_delete=models.PROTECT,
    )

    # "+" means no reverse relation to lookup applications from Website
    current_websites = models.ManyToManyField(
        "registrar.Website",
        blank=True,
        related_name="current+",
        verbose_name="websites",
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
        verbose_name="contacts",
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

    # submission date records when application is submitted
    submission_date = models.DateField(
        null=True,
        blank=True,
        default=None,
        help_text="Date submitted",
    )

    notes = models.TextField(
        null=True,
        blank=True,
        help_text="Notes about this request",
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

    def _send_status_update_email(self, new_status, email_template, email_template_subject, send_email=True):
        """Send a status update email to the submitter.

        The email goes to the email address that the submitter gave as their
        contact information. If there is not submitter information, then do
        nothing.

        send_email: bool -> Used to bypass the send_templated_email function, in the event
        we just want to log that an email would have been sent, rather than actually sending one.
        """

        if self.submitter is None or self.submitter.email is None:
            logger.warning(f"Cannot send {new_status} email, no submitter email address.")
            return None

        if not send_email:
            logger.info(f"Email was not sent. Would send {new_status} email: {self.submitter.email}")
            return None

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
        field="status",
        source=[
            ApplicationStatus.STARTED,
            ApplicationStatus.IN_REVIEW,
            ApplicationStatus.ACTION_NEEDED,
            ApplicationStatus.WITHDRAWN,
        ],
        target=ApplicationStatus.SUBMITTED,
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

        # Update submission_date to today
        self.submission_date = timezone.now().date()
        self.save()

        self._send_status_update_email(
            "submission confirmation",
            "emails/submission_confirmation.txt",
            "emails/submission_confirmation_subject.txt",
        )

    @transition(
        field="status",
        source=[
            ApplicationStatus.SUBMITTED,
            ApplicationStatus.ACTION_NEEDED,
            ApplicationStatus.APPROVED,
            ApplicationStatus.REJECTED,
            ApplicationStatus.INELIGIBLE,
        ],
        target=ApplicationStatus.IN_REVIEW,
    )
    def in_review(self):
        """Investigate an application that has been submitted.

        This action is logged."""
        literal = DomainApplication.ApplicationStatus.IN_REVIEW
        # Check if the tuple exists, then grab its value
        in_review = literal if literal is not None else "In Review"
        logger.info(f"A status change occurred. {self} was changed to '{in_review}'")

    @transition(
        field="status",
        source=[
            ApplicationStatus.IN_REVIEW,
            ApplicationStatus.APPROVED,
            ApplicationStatus.REJECTED,
            ApplicationStatus.INELIGIBLE,
        ],
        target=ApplicationStatus.ACTION_NEEDED,
    )
    def action_needed(self):
        """Send back an application that is under investigation or rejected.

        This action is logged."""
        literal = DomainApplication.ApplicationStatus.ACTION_NEEDED
        # Check if the tuple is setup correctly, then grab its value
        action_needed = literal if literal is not None else "Action Needed"
        logger.info(f"A status change occurred. {self} was changed to '{action_needed}'")

    @transition(
        field="status",
        source=[
            ApplicationStatus.SUBMITTED,
            ApplicationStatus.IN_REVIEW,
            ApplicationStatus.ACTION_NEEDED,
            ApplicationStatus.REJECTED,
        ],
        target=ApplicationStatus.APPROVED,
    )
    def approve(self, send_email=True):
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
        DomainInformation.create_from_da(domain_application=self, domain=created_domain)

        # create the permission for the user
        UserDomainRole = apps.get_model("registrar.UserDomainRole")
        UserDomainRole.objects.get_or_create(
            user=self.creator, domain=created_domain, role=UserDomainRole.Roles.MANAGER
        )

        self._send_status_update_email(
            "application approved",
            "emails/status_change_approved.txt",
            "emails/status_change_approved_subject.txt",
            send_email,
        )

    @transition(
        field="status",
        source=[ApplicationStatus.SUBMITTED, ApplicationStatus.IN_REVIEW, ApplicationStatus.ACTION_NEEDED],
        target=ApplicationStatus.WITHDRAWN,
    )
    def withdraw(self):
        """Withdraw an application that has been submitted."""
        self._send_status_update_email(
            "withdraw",
            "emails/domain_request_withdrawn.txt",
            "emails/domain_request_withdrawn_subject.txt",
        )

    @transition(
        field="status",
        source=[ApplicationStatus.IN_REVIEW, ApplicationStatus.ACTION_NEEDED, ApplicationStatus.APPROVED],
        target=ApplicationStatus.REJECTED,
        conditions=[domain_is_not_active],
    )
    def reject(self):
        """Reject an application that has been submitted.

        As side effects this will delete the domain and domain_information
        (will cascade), and send an email notification."""
        if self.status == self.ApplicationStatus.APPROVED:
            try:
                domain_state = self.approved_domain.state
                # Only reject if it exists on EPP
                if domain_state != Domain.State.UNKNOWN:
                    self.approved_domain.deletedInEpp()
                    self.approved_domain.save()
                self.approved_domain.delete()
                self.approved_domain = None
            except Exception as err:
                logger.error(err)
                logger.error("Can't query an approved domain while attempting a DA reject()")

        self._send_status_update_email(
            "action needed",
            "emails/status_change_rejected.txt",
            "emails/status_change_rejected_subject.txt",
        )

    @transition(
        field="status",
        source=[
            ApplicationStatus.IN_REVIEW,
            ApplicationStatus.ACTION_NEEDED,
            ApplicationStatus.APPROVED,
            ApplicationStatus.REJECTED,
        ],
        target=ApplicationStatus.INELIGIBLE,
        conditions=[domain_is_not_active],
    )
    def reject_with_prejudice(self):
        """The applicant is a bad actor, reject with prejudice.

        No email As a side effect, but we block the applicant from editing
        any existing domains/applications and from submitting new aplications.
        We do this by setting an ineligible status on the user, which the
        permissions classes test against. This will also delete the domain
        and domain_information (will cascade) when they exist."""

        if self.status == self.ApplicationStatus.APPROVED:
            try:
                domain_state = self.approved_domain.state
                # Only reject if it exists on EPP
                if domain_state != Domain.State.UNKNOWN:
                    self.approved_domain.deletedInEpp()
                    self.approved_domain.save()
                self.approved_domain.delete()
                self.approved_domain = None
            except Exception as err:
                logger.error(err)
                logger.error("Can't query an approved domain while attempting a DA reject_with_prejudice()")

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

    def show_about_your_organization(self) -> bool:
        """Show this step if this is a special district or interstate."""
        user_choice = self.organization_type
        return user_choice in [
            DomainApplication.OrganizationChoices.SPECIAL_DISTRICT,
            DomainApplication.OrganizationChoices.INTERSTATE,
        ]

    def has_rationale(self) -> bool:
        """Does this application have no_other_contacts_rationale?"""
        return bool(self.no_other_contacts_rationale)

    def has_other_contacts(self) -> bool:
        """Does this application have other contacts listed?"""
        return self.other_contacts.exists()

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
