from .utility.time_stamped_model import TimeStampedModel
from django.db import models
import logging
from registrar.utility.constants import BranchChoices

logger = logging.getLogger(__name__)


class FederalAgency(TimeStampedModel):
    class Meta:
        verbose_name = "Federal agency"
        verbose_name_plural = "Federal agencies"

    agency = models.CharField(
        null=True,
        blank=False,
        verbose_name="Federal agency",
    )

    federal_type = models.CharField(
        max_length=20,
        choices=BranchChoices.choices,
        null=True,
        blank=True,
    )

    acronym = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text="Acronym commonly used to reference the federal agency (Optional)",
    )

    is_fceb = models.BooleanField(
        null=True,
        blank=True,
        verbose_name="FCEB",
        help_text="Federal Civilian Executive Branch (FCEB)",
    )

    def __str__(self) -> str:
        return f"{self.agency}"

    def create_federal_agencies(apps, schema_editor):
        """This method gets run from a data migration to prepopulate data
        regarding federal agencies."""

        # Hard to pass self to these methods as the calls from migrations
        # are only expecting apps and schema_editor, so we'll just define
        # apps, schema_editor in the local scope instead

        AGENCIES = [
            "Administrative Conference of the United States",
            "Advisory Council on Historic Preservation",
            "American Battle Monuments Commission",
            "AMTRAK",
            "Appalachian Regional Commission",
            ("Appraisal Subcommittee of the Federal Financial " "Institutions Examination Council"),
            "Architect of the Capitol",
            "Armed Forces Retirement Home",
            "Barry Goldwater Scholarship and Excellence in Education Foundation",
            "Central Intelligence Agency",
            "Christopher Columbus Fellowship Foundation",
            "Civil Rights Cold Case Records Review Board",
            "Commission for the Preservation of America's Heritage Abroad",
            "Commission of Fine Arts",
            "Committee for Purchase From People Who Are Blind or Severely Disabled",
            "Commodity Futures Trading Commission",
            "Congressional Budget Office",
            "Consumer Financial Protection Bureau",
            "Consumer Product Safety Commission",
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
            "Federal Trade Commission",
            "General Services Administration",
            "gov Administration",
            "Government Accountability Office",
            "Government Publishing Office",
            "Gulf Coast Ecosystem Restoration Council",
            "Harry S. Truman Scholarship Foundation",
            "Institute of Museum and Library Services",
            "Institute of Peace",
            "Inter-American Foundation",
            "International Boundary and Water Commission: United States and Mexico",
            "International Boundary Commission: United States and Canada",
            "International Joint Commission: United States and Canada",
            "James Madison Memorial Fellowship Foundation",
            "Japan-U.S. Friendship Commission",
            "John F. Kennedy Center for the Performing Arts",
            "Legal Services Corporation",
            "Legislative Branch",
            "Library of Congress",
            "Marine Mammal Commission",
            "Medicaid and CHIP Payment and Access Commission",
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

        FederalAgency = apps.get_model("registrar", "FederalAgency")
        logger.info("Creating federal agency table.")

        try:
            agencies = [FederalAgency(agency=agency) for agency in AGENCIES]
            FederalAgency.objects.bulk_create(agencies)
        except Exception as e:
            logger.error(f"Error creating federal agencies: {e}")

    @classmethod
    def get_non_federal_agency(cls):
        """Returns the non-federal agency."""
        return FederalAgency.objects.filter(agency="Non-Federal Agency").first()
