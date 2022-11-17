from auditlog.registry import auditlog  # type: ignore

from .contact import Contact
from .domain_application import DomainApplication
from .user_profile import UserProfile
from .user import User
from .website import Website

__all__ = [
    "Contact",
    "DomainApplication",
    "UserProfile",
    "User",
    "Website",
]

auditlog.register(Contact)
auditlog.register(DomainApplication)
auditlog.register(UserProfile)
auditlog.register(User)
auditlog.register(Website)
