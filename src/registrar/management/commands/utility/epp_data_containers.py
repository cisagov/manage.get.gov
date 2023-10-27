from dataclasses import dataclass
from enum import Enum
from typing import Optional


@dataclass
class AgencyAdhoc:
    """Defines the structure given in the AGENCY_ADHOC file"""

    agencyid: Optional[int] = None
    agencyname: Optional[str] = None
    active: Optional[str] = None
    isfederal: Optional[str] = None


@dataclass
class DomainAdditionalData:
    """Defines the structure given in the DOMAIN_ADDITIONAL file"""

    domainname: Optional[str] = None
    domaintypeid: Optional[int] = None
    authorityid: Optional[int] = None
    orgid: Optional[int] = None
    securitycontact_email: Optional[str] = None
    dnsseckeymonitor: Optional[str] = None
    domainpurpose: Optional[str] = None


@dataclass
class DomainTypeAdhoc:
    """Defines the structure given in the DOMAIN_ADHOC file"""

    domaintypeid: Optional[int] = None
    domaintype: Optional[str] = None
    code: Optional[str] = None
    active: Optional[str] = None


@dataclass
class OrganizationAdhoc:
    """Defines the structure given in the ORGANIZATION_ADHOC file"""

    orgid: Optional[int] = None
    orgname: Optional[str] = None
    orgstreet: Optional[str] = None
    orgcity: Optional[str] = None
    orgstate: Optional[str] = None
    orgzip: Optional[str] = None
    orgcountrycode: Optional[str] = None


class EnumFilenames(Enum):
    """Returns a tuple mapping for (filetype, default_file_name).

    For instance, AGENCY_ADHOC = ("agency_adhoc", "agency.adhoc.dotgov.txt")
    """

    AGENCY_ADHOC = ("agency_adhoc", "agency.adhoc.dotgov.txt")
    DOMAIN_ADDITIONAL = (
        "domain_additional",
        "domainadditionaldatalink.adhoc.dotgov.txt",
    )
    DOMAIN_ADHOC = ("domain_adhoc", "domaintypes.adhoc.dotgov.txt")
    ORGANIZATION_ADHOC = ("organization_adhoc", "organization.adhoc.dotgov.txt")
