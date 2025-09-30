from auditlog.registry import auditlog
from .contact import Contact
from .domain_request import DomainRequest
from .domain_information import DomainInformation
from .domain import Domain
from .draft_domain import DraftDomain
from .federal_agency import FederalAgency
from .host_ip import HostIP
from .host import Host
from .domain_invitation import DomainInvitation
from .user_domain_role import UserDomainRole
from .public_contact import PublicContact
from .dns.dns_account import DnsAccount
from .dns.dns_vendor import DnsVendor
from .dns.vendor_dns_account import VendorDnsAccount
from .dns.dns_account_vendor_dns_account import DnsAccount_VendorDnsAccount
from .dns.dns_zone import DnsZone
from .dns.vendor_dns_zone import VendorDnsZone
from .dns.dns_zone_vendor_dns_zone import DnsZone_VendorDnsZone
from .dns.dns_record import DnsRecord
from .dns.vendor_dns_record import VendorDnsRecord
from .dns.dns_record_vendor_dns_record import DnsRecord_VendorDnsRecord

# IMPORTANT: UserPortfolioPermission must be before PortfolioInvitation.
# PortfolioInvitation imports from UserPortfolioPermission, so you will get a circular import otherwise.
from .user_portfolio_permission import UserPortfolioPermission
from .portfolio_invitation import PortfolioInvitation
from .user import User
from .user_group import UserGroup
from .website import Website
from .transition_domain import TransitionDomain
from .verified_by_staff import VerifiedByStaff
from .waffle_flag import WaffleFlag
from .portfolio import Portfolio
from .domain_group import DomainGroup
from .suborganization import Suborganization
from .senior_official import SeniorOfficial
from .allowed_email import AllowedEmail


__all__ = [
    "Contact",
    "DomainRequest",
    "DomainInformation",
    "Domain",
    "DraftDomain",
    "DomainInvitation",
    "FederalAgency",
    "HostIP",
    "Host",
    "UserDomainRole",
    "PublicContact",
    "User",
    "UserGroup",
    "Website",
    "TransitionDomain",
    "VerifiedByStaff",
    "WaffleFlag",
    "PortfolioInvitation",
    "Portfolio",
    "DomainGroup",
    "Suborganization",
    "SeniorOfficial",
    "UserPortfolioPermission",
    "AllowedEmail",
    "DnsVendor",
    "DnsAccount",
    "VendorDnsAccount",
    "DnsAccount_VendorDnsAccount",
    "DnsZone",
    "VendorDnsZone",
    "DnsZone_VendorDnsZone",
    "DnsRecord",
    "VendorDnsRecord",
    "DnsRecord_VendorDnsRecord"
]

auditlog.register(Contact)
auditlog.register(DomainRequest)
auditlog.register(Domain)
auditlog.register(DraftDomain)
auditlog.register(DomainInvitation)
auditlog.register(DomainInformation)
auditlog.register(FederalAgency)
auditlog.register(HostIP)
auditlog.register(Host)
auditlog.register(UserDomainRole)
auditlog.register(PublicContact)
auditlog.register(User, m2m_fields=["user_permissions", "groups"])
auditlog.register(UserGroup, m2m_fields=["permissions"])
auditlog.register(Website)
auditlog.register(TransitionDomain)
auditlog.register(VerifiedByStaff)
auditlog.register(WaffleFlag)
auditlog.register(PortfolioInvitation)
auditlog.register(Portfolio)
auditlog.register(DomainGroup)
auditlog.register(Suborganization)
auditlog.register(SeniorOfficial)
auditlog.register(UserPortfolioPermission)
auditlog.register(AllowedEmail)
