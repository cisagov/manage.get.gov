from enum import IntEnum


class BlankValueError(ValueError):
    pass


class ExtraDotsError(ValueError):
    pass


class DomainUnavailableError(ValueError):
    pass


class RegistrySystemError(ValueError):
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
contact help@get.gov.
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

    @classmethod
    def get_error_mapping(self, code=None):
        return self._error_mapping.get(code)


class NameserverErrorCodes(IntEnum):
    """Used in the NameserverError class for
    error mapping.
    Overview of nameserver error codes:
        - 1 MISSING_IP  ip address is missing for a nameserver
        - 2 GLUE_RECORD_NOT_ALLOWED a host has a nameserver
                                    value but is not a subdomain
        - 3 INVALID_IP  invalid ip address format or invalid version
        - 4 TOO_MANY_HOSTS  more than the max allowed host values
        - 5 MISSING_HOST host is missing for a nameserver
        - 6 INVALID_HOST host is invalid for a nameserver
        - 7 DUPLICATE_HOST host is a duplicate
        - 8 BAD_DATA bad data input for nameserver
    """

    MISSING_IP = 1
    GLUE_RECORD_NOT_ALLOWED = 2
    INVALID_IP = 3
    TOO_MANY_HOSTS = 4
    MISSING_HOST = 5
    INVALID_HOST = 6
    DUPLICATE_HOST = 7
    BAD_DATA = 8


class NameserverError(Exception):
    """
    NameserverError class used to raise exceptions on
    the nameserver getter
    """

    _error_mapping = {
        NameserverErrorCodes.MISSING_IP: ("Using your domain for a name server requires an IP address"),
        NameserverErrorCodes.GLUE_RECORD_NOT_ALLOWED: ("Name server address does not match domain name"),
        NameserverErrorCodes.INVALID_IP: ("{}: Enter an IP address in the required format."),
        NameserverErrorCodes.TOO_MANY_HOSTS: ("Too many hosts provided, you may not have more than 13 nameservers."),
        NameserverErrorCodes.MISSING_HOST: ("Name server must be provided to enter IP address."),
        NameserverErrorCodes.INVALID_HOST: ("Enter a name server in the required format, like ns1.example.com"),
        NameserverErrorCodes.DUPLICATE_HOST: ("Remove duplicate entry"),
        NameserverErrorCodes.BAD_DATA: (
            "There’s something wrong with the name server information you provided. "
            "If you need help email us at help@get.gov."
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


class DsDataErrorCodes(IntEnum):
    """Used in the DsDataError class for
    error mapping.
    Overview of ds data error codes:
        - 1 BAD_DATA  bad data input in ds data
        - 2 INVALID_DIGEST_SHA1 invalid digest for digest type SHA-1
        - 3 INVALID_DIGEST_SHA256 invalid digest for digest type SHA-256
        - 4 INVALID_DIGEST_CHARS invalid chars in digest
        - 5 INVALID_KEYTAG_SIZE invalid key tag size > 65535
    """

    BAD_DATA = 1
    INVALID_DIGEST_SHA1 = 2
    INVALID_DIGEST_SHA256 = 3
    INVALID_DIGEST_CHARS = 4
    INVALID_KEYTAG_SIZE = 5


class DsDataError(Exception):
    """
    DsDataError class used to raise exceptions on
    the ds data getter
    """

    _error_mapping = {
        DsDataErrorCodes.BAD_DATA: (
            "There’s something wrong with the DS data you provided. If you need help email us at help@get.gov."
        ),
        DsDataErrorCodes.INVALID_DIGEST_SHA1: ("SHA-1 digest must be exactly 40 characters."),
        DsDataErrorCodes.INVALID_DIGEST_SHA256: ("SHA-256 digest must be exactly 64 characters."),
        DsDataErrorCodes.INVALID_DIGEST_CHARS: ("Digest must contain only alphanumeric characters [0-9,a-f]."),
        DsDataErrorCodes.INVALID_KEYTAG_SIZE: ("Key tag must be less than 65535"),
    }

    def __init__(self, *args, code=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.code = code
        if self.code in self._error_mapping:
            self.message = self._error_mapping.get(self.code)

    def __str__(self):
        return f"{self.message}"


class SecurityEmailErrorCodes(IntEnum):
    """Used in the SecurityEmailError class for
    error mapping.
    Overview of security email error codes:
        - 1 BAD_DATA  bad data input in security email
    """

    BAD_DATA = 1


class SecurityEmailError(Exception):
    """
    SecurityEmailError class used to raise exceptions on
    the security email form
    """

    _error_mapping = {
        SecurityEmailErrorCodes.BAD_DATA: ("Enter an email address in the required format, like name@example.com.")
    }

    def __init__(self, *args, code=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.code = code
        if self.code in self._error_mapping:
            self.message = self._error_mapping.get(self.code)

    def __str__(self):
        return f"{self.message}"
