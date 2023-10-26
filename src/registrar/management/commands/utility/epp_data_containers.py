from dataclasses import dataclass
from typing import Optional

@dataclass
class AgencyAdhoc():
    """Defines the structure given in the given AGENCY_ADHOC file"""
    agencyid: Optional[int] = None
    agencyname: Optional[str] = None
    active: Optional[bool] = None
    isfederal: Optional[bool] = None


@dataclass
class DomainAdditionalData():
    """Defines the structure given in the given DOMAIN_ADDITIONAL file"""
    domainname: Optional[str] = None
    domaintypeid: Optional[int] = None
    authorityid: Optional[int] = None
    orgid: Optional[int] = None
    securitycontact_email: Optional[str] = None
    dnsseckeymonitor: Optional[str] = None
    domainpurpose: Optional[str] = None

@dataclass
class DomainTypeAdhoc():
    """Defines the structure given in the given DOMAIN_ADHOC file"""
    domaintypeid: Optional[int] = None
    domaintype: Optional[str] = None
    code: Optional[str] = None
    active: Optional[bool] = None

@dataclass
class OrganizationAdhoc():
    """Defines the structure given in the given ORGANIZATION_ADHOC file"""
    orgid: Optional[int] = None
    orgname: Optional[str] = None
    orgstreet: Optional[str] = None
    orgcity: Optional[str] = None
    orgstate: Optional[str] = None
    orgzip: Optional[str] = None
    orgcountrycode: Optional[str] = None