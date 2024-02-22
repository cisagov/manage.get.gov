"""
A list of helper classes to facilitate handling data from verisign data exports.

Regarding our dataclasses:
Not intended to be used as models but rather as an alternative to storing as a dictionary.
By keeping it as a dataclass instead of a dictionary, we can maintain data consistency.
"""  # noqa

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import List, Optional


@dataclass
class AgencyAdhoc:
    """Defines the structure given in the AGENCY_ADHOC file"""

    agencyid: Optional[int] = field(default=None, repr=True)
    agencyname: Optional[str] = field(default=None, repr=True)
    active: Optional[str] = field(default=None, repr=True)
    isfederal: Optional[str] = field(default=None, repr=True)


@dataclass
class DomainAdditionalData:
    """Defines the structure given in the DOMAIN_ADDITIONAL file"""

    domainname: Optional[str] = field(default=None, repr=True)
    domaintypeid: Optional[int] = field(default=None, repr=True)
    authorityid: Optional[int] = field(default=None, repr=True)
    orgid: Optional[int] = field(default=None, repr=True)
    securitycontactemail: Optional[str] = field(default=None, repr=True)
    dnsseckeymonitor: Optional[str] = field(default=None, repr=True)
    domainpurpose: Optional[str] = field(default=None, repr=True)


@dataclass
class DomainTypeAdhoc:
    """Defines the structure given in the DOMAIN_ADHOC file"""

    domaintypeid: Optional[int] = field(default=None, repr=True)
    domaintype: Optional[str] = field(default=None, repr=True)
    code: Optional[str] = field(default=None, repr=True)
    active: Optional[str] = field(default=None, repr=True)


@dataclass
class OrganizationAdhoc:
    """Defines the structure given in the ORGANIZATION_ADHOC file"""

    orgid: Optional[int] = field(default=None, repr=True)
    orgname: Optional[str] = field(default=None, repr=True)
    orgstreet: Optional[str] = field(default=None, repr=True)
    orgcity: Optional[str] = field(default=None, repr=True)
    orgstate: Optional[str] = field(default=None, repr=True)
    orgzip: Optional[str] = field(default=None, repr=True)
    orgcountrycode: Optional[str] = field(default=None, repr=True)


@dataclass
class AuthorityAdhoc:
    """Defines the structure given in the AUTHORITY_ADHOC file"""

    authorityid: Optional[int] = field(default=None, repr=True)
    firstname: Optional[str] = field(default=None, repr=True)
    middlename: Optional[str] = field(default=None, repr=True)
    lastname: Optional[str] = field(default=None, repr=True)
    email: Optional[str] = field(default=None, repr=True)
    phonenumber: Optional[str] = field(default=None, repr=True)
    agencyid: Optional[int] = field(default=None, repr=True)
    addlinfo: Optional[List[str]] = field(default=None, repr=True)


@dataclass
class DomainEscrow:
    """Defines the structure given in the DOMAIN_ESCROW file"""

    domainname: Optional[str] = field(default=None, repr=True)
    creationdate: Optional[date] = field(default=None, repr=True)
    expirationdate: Optional[date] = field(default=None, repr=True)


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
