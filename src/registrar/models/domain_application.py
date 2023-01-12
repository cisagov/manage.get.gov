from __future__ import annotations
from typing import Union

from django.apps import apps
from django.db import models
from django_fsm import FSMField, transition  # type: ignore

from .utility.time_stamped_model import TimeStampedModel


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
        "",
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
        help_text="Type of Organization",
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
        help_text="Purpose of your domain",
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

    def show_organization_federal(self) -> bool:
        """Show this step if the answer to the first question was "federal"."""
        user_choice = self.organization_type
        return user_choice == DomainApplication.OrganizationChoices.FEDERAL

    def show_organization_election(self) -> bool:
        """Show this step if the answer to the first question implies it.

        This shows for answers that aren't "Federal" or "Interstate".
        """
        user_choice = self.organization_type
        excluded = [
            DomainApplication.OrganizationChoices.FEDERAL,
            DomainApplication.OrganizationChoices.INTERSTATE,
        ]
        return bool(user_choice and user_choice not in excluded)

    def show_type_of_work(self) -> bool:
        """Show this step if this is a special district or interstate."""
        user_choice = self.organization_type
        return user_choice in [
            DomainApplication.OrganizationChoices.SPECIAL_DISTRICT,
            DomainApplication.OrganizationChoices.INTERSTATE,
        ]

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
