from enum import IntEnum


class BlankValueError(ValueError):
    pass


class ExtraDotsError(ValueError):
    pass


class DomainUnavailableError(ValueError):
    pass


class ActionNotAllowed(Exception):
    """User accessed an action that is not
    allowed by the current state"""

    pass


class GenericErrorCodes(IntEnum):
    """Used across the registrar for
    error mapping.
    Overview of generic error codes:
        - 1 GENERIC_ERROR a generic value error
        - 2 CANNOT_CONTACT_REGISTRY a connection error w registry
    """

    GENERIC_ERROR = 1
    CANNOT_CONTACT_REGISTRY = 2


class GenericError(Exception):
    """
    GenericError class used to raise exceptions across
    the registrar
    """

    _error_mapping = {
        GenericErrorCodes.CANNOT_CONTACT_REGISTRY: """
We’re experiencing a system connection error. Please wait a few minutes
and try again. If you continue to receive this error after a few tries,
contact help@get.gov
        """,
        GenericErrorCodes.GENERIC_ERROR: ("Value entered was wrong."),
    }

    def __init__(self, *args, code=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.code = code
        if self.code in self._error_mapping:
            self.message = self._error_mapping.get(self.code)

    def __str__(self):
        return f"{self.message}"


class NameserverErrorCodes(IntEnum):
    """Used in the NameserverError class for
    error mapping.
    Overview of nameserver error codes:
        - 1 MISSING_IP  ip address is missing for a nameserver
        - 2 GLUE_RECORD_NOT_ALLOWED a host has a nameserver
                                    value but is not a subdomain
        - 3 INVALID_IP  invalid ip address format or invalid version
        - 4 TOO_MANY_HOSTS  more than the max allowed host values
        - 5 UNABLE_TO_UPDATE_DOMAIN unable to update the domain
        - 6 MISSING_HOST host is missing for a nameserver
    """

    MISSING_IP = 1
    GLUE_RECORD_NOT_ALLOWED = 2
    INVALID_IP = 3
    TOO_MANY_HOSTS = 4
    UNABLE_TO_UPDATE_DOMAIN = 5
    MISSING_HOST = 6


class NameserverError(Exception):
    """
    NameserverError class used to raise exceptions on
    the nameserver getter
    """

    _error_mapping = {
        NameserverErrorCodes.MISSING_IP: (
            "Using your domain for a name server requires an IP address"
        ),
        NameserverErrorCodes.GLUE_RECORD_NOT_ALLOWED: (
            "Name server address does not match domain name"
        ),
        NameserverErrorCodes.INVALID_IP: (
            "{}: Enter an IP address in the required format."
        ),
        NameserverErrorCodes.TOO_MANY_HOSTS: (
            "Too many hosts provided, you may not have more than 13 nameservers."
        ),
        NameserverErrorCodes.UNABLE_TO_UPDATE_DOMAIN: (
            "Unable to update domain, changes were not applied."
            "Check logs as a Registry Error is the likely cause"
        ),
        NameserverErrorCodes.MISSING_HOST: (
            "Name server must be provided to enter IP address."
        ),
    }

    def __init__(self, *args, code=None, nameserver=None, ip=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.code = code
        if self.code in self._error_mapping:
            self.message = self._error_mapping.get(self.code)
            if nameserver is not None and ip is not None:
                self.message = self.message.format(str(nameserver))
            elif nameserver is not None:
                self.message = self.message.format(str(nameserver))
            elif ip is not None:
                self.message = self.message.format(str(ip))

    def __str__(self):
        return f"{self.message}"
