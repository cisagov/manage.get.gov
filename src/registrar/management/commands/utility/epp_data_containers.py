"""
A list of helper classes to facilitate handling data from verisign data exports.

Regarding our dataclasses:
Not intended to be used as models but rather as an alternative to storing as a dictionary.
By keeping it as a dataclass instead of a dictionary, we can maintain data consistency.
"""
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import List, Optional


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
    securitycontactemail: Optional[str] = None
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


@dataclass
class AuthorityAdhoc:
    """Defines the structure given in the AUTHORITY_ADHOC file"""
    authorityid: Optional[int] = None
    firstname: Optional[str] = None
    middlename: Optional[str] = None
    lastname: Optional[str] = None
    email: Optional[str] = None
    phonenumber: Optional[str] = None
    agencyid: Optional[int] = None
    addlinfo: Optional[List[str]] = None

@dataclass
class DomainEscrow:
    """Defines the structure given in the DOMAIN_ESCROW file"""
    domainname: Optional[str] = None
    creationdate: Optional[date] = None
    expirationdate: Optional[date] = None


class EnumFilenames(Enum):
    """Returns a tuple mapping for (filetype, default_file_name).

    For instance, AGENCY_ADHOC = ("agency_adhoc", "agency.adhoc.dotgov.txt")
    """

    # We are sourcing data from many different locations, so its better to track this
    # as an Enum rather than multiple spread out variables.
    # We store the "type" as [0], and we store the "default_filepath" as [1].
    AGENCY_ADHOC = ("agency_adhoc", "agency.adhoc.dotgov.txt")
    DOMAIN_ADDITIONAL = (
        "domain_additional",
        "domainadditionaldatalink.adhoc.dotgov.txt",
    )
    DOMAIN_ESCROW = ("domain_escrow", "escrow_domains.daily.dotgov.GOV.txt")
    DOMAIN_ADHOC = ("domain_adhoc", "domaintypes.adhoc.dotgov.txt")
    ORGANIZATION_ADHOC = ("organization_adhoc", "organization.adhoc.dotgov.txt")
    AUTHORITY_ADHOC = ("authority_adhoc", "authority.adhoc.dotgov.txt")
