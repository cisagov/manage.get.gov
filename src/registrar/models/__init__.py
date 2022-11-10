from auditlog.registry import auditlog  # type: ignore

from .models import User, UserProfile, Contact, Website, DomainApplication

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
