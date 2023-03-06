from auditlog.registry import auditlog  # type: ignore

from .contact import Contact
from .domain_application import DomainApplication
from .domain import Domain
from .host_ip import HostIP
from .host import Host
from .nameserver import Nameserver
from .user_domain_role import UserDomainRole
from .user_profile import UserProfile
from .user import User
from .website import Website

__all__ = [
    "Contact",
    "DomainApplication",
    "Domain",
    "HostIP",
    "Host",
    "Nameserver",
    "UserDomainRole",
    "UserProfile",
    "User",
    "Website",
]

auditlog.register(Contact)
auditlog.register(DomainApplication)
auditlog.register(Domain)
auditlog.register(HostIP)
auditlog.register(Host)
auditlog.register(Nameserver)
auditlog.register(UserDomainRole)
auditlog.register(UserProfile)
auditlog.register(User)
auditlog.register(Website)
