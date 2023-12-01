import re

from api.views import check_domain_available
from registrar.utility import errors
from registrar.utility.errors import GenericError, GenericErrorCodes


class DomainHelper:
    """Utility functions and constants for domain names."""

    # a domain name is alphanumeric or hyphen, up to 63 characters, doesn't
    # begin or end with a hyphen, followed by a TLD of 2-6 alphabetic characters
    DOMAIN_REGEX = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)\.[A-Za-z]{2,6}$")

    # a domain can be no longer than 253 characters in total
    MAX_LENGTH = 253

    @classmethod
    def string_could_be_domain(cls, domain: str | None) -> bool:
        """Return True if the string could be a domain name, otherwise False."""
        if not isinstance(domain, str):
            return False
        return bool(cls.DOMAIN_REGEX.match(domain))

    @classmethod
    def validate(cls, domain: str | None, blank_ok=False) -> str:
        """Attempt to determine if a domain name could be requested."""
        if domain is None:
            raise errors.BlankValueError()
        if not isinstance(domain, str):
            raise ValueError("Domain name must be a string")
        domain = domain.lower().strip()
        if domain == "":
            if blank_ok:
                return domain
            else:
                raise errors.BlankValueError()
        if domain.endswith(".gov"):
            domain = domain[:-4]
        if "." in domain:
            raise errors.ExtraDotsError()
        if not DomainHelper.string_could_be_domain(domain + ".gov"):
            raise ValueError()
        try:
            if not check_domain_available(domain):
                raise errors.DomainUnavailableError()
        except Exception:
            raise errors.RegistrySystemError()
        return domain

    @classmethod
    def sld(cls, domain: str):
        """
        Get the second level domain. Example: `gsa.gov` -> `gsa`.

        If no TLD is present, returns the original string.
        """
        return domain.split(".")[0]

    @classmethod
    def tld(cls, domain: str):
        """Get the top level domain. Example: `gsa.gov` -> `gov`."""
        parts = domain.rsplit(".")
        return parts[-1] if len(parts) > 1 else ""
