import logging

from enum import IntEnum

logger = logging.getLogger(__name__)


class BlankValueError(ValueError):
    pass


class ExtraDotsError(ValueError):
    pass


class DomainUnavailableError(ValueError):
    pass


class RegistrySystemError(ValueError):
    pass


class InvalidDomainError(ValueError):
    """Error class for situations where an invalid domain is supplied"""

    pass


class InvitationError(Exception):
    """Base exception for invitation-related errors."""

    pass


class AlreadyDomainManagerError(InvitationError):
    """Raised when the user is already a manager for the domain."""

    def __init__(self, email):
        super().__init__(f"An unexpected error occurred: {email} could not be added to this domain.")


class AlreadyDomainInvitedError(InvitationError):
    """Raised when the user has already been invited to the domain."""

    def __init__(self, email):
        super().__init__(f"{email} has already been invited to this domain.")


class MissingEmailError(InvitationError):
    """Raised when the requestor has no email associated with their account."""

    def __init__(self, email=None, domain=None, portfolio=None):
        # Default message if no additional info is provided
        message = "Can't send invitation email. No email is associated with your user account."

        super().__init__(message)


class OutsideOrgMemberError(InvitationError):
    """
    Error raised when an org member tries adding a user from a different .gov org.
    To be deleted when users can be members of multiple orgs.
    """

    def __init__(self, email=None):
        # Default message if no additional info is provided
        message = "Can not invite member to this organization."
        if email:
            message = f"{email} is not a member of this organization."
        super().__init__(message)


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
        GenericErrorCodes.CANNOT_CONTACT_REGISTRY: (
            "We’re experiencing a system error. Please wait a few minutes "
            "and try again. If you continue to get this error, "
            "contact help@get.gov."
        ),
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
    def get_error_message(self, code=None):
        return self._error_mapping.get(code)


class FSMErrorCodes(IntEnum):
    """Used when doing FSM transitions.
    Overview of generic error codes:
        - 1 APPROVE_DOMAIN_IN_USE The domain is already in use
        - 2 NO_INVESTIGATOR No investigator is assigned
        - 3 INVESTIGATOR_NOT_STAFF Investigator is a non-staff user
        - 4 NO_REJECTION_REASON No rejection reason is specified
        - 5 NO_ACTION_NEEDED_REASON No action needed reason is specified
        - 6 DOMAIN_IS_PENDING_DELETE Domain is in pending delete state
    """

    APPROVE_DOMAIN_IN_USE = 1
    NO_INVESTIGATOR = 2
    INVESTIGATOR_NOT_STAFF = 3
    NO_REJECTION_REASON = 4
    NO_ACTION_NEEDED_REASON = 5
    DOMAIN_IS_PENDING_DELETE = 6


class FSMDomainRequestError(Exception):
    """
    Used to raise exceptions when doing FSM Transitions.
    Uses `FSMErrorCodes` as an enum.
    """

    _error_mapping = {
        FSMErrorCodes.APPROVE_DOMAIN_IN_USE: ("Cannot approve. Requested domain is already in use."),
        FSMErrorCodes.NO_INVESTIGATOR: ("Investigator is required for this status."),
        FSMErrorCodes.INVESTIGATOR_NOT_STAFF: ("Investigator is not a staff user."),
        FSMErrorCodes.NO_REJECTION_REASON: ("A reason is required for this status."),
        FSMErrorCodes.NO_ACTION_NEEDED_REASON: ("A reason is required for this status."),
        FSMErrorCodes.DOMAIN_IS_PENDING_DELETE: ("Domain of same name is currently in pending delete state."),
    }

    def __init__(self, *args, code=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.code = code
        if self.code in self._error_mapping:
            self.message = self._error_mapping.get(self.code)

    def __str__(self):
        return f"{self.message}"

    @classmethod
    def get_error_message(cls, code=None):
        return cls._error_mapping.get(code)


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
        NameserverErrorCodes.MISSING_IP: ("Using your domain for a name server requires an IP address."),
        NameserverErrorCodes.GLUE_RECORD_NOT_ALLOWED: ("Name server address does not match domain name"),
        NameserverErrorCodes.INVALID_IP: ("{}: Enter an IP address in the required format."),
        NameserverErrorCodes.TOO_MANY_HOSTS: ("You can't have more than 13 nameservers."),
        NameserverErrorCodes.MISSING_HOST: ("You must provide a name server to enter an IP address."),
        NameserverErrorCodes.INVALID_HOST: ("Enter a name server in the required format, like ns1.example.com"),
        NameserverErrorCodes.DUPLICATE_HOST: (
            "You already entered this name server address. Name server addresses must be unique."
        ),
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
        - 6 INVALID_KEYTAG_CHARS invalid key tag, not numeric
    """

    BAD_DATA = 1
    INVALID_DIGEST_SHA1 = 2
    INVALID_DIGEST_SHA256 = 3
    INVALID_DIGEST_CHARS = 4
    INVALID_KEYTAG_SIZE = 5
    INVALID_KEYTAG_CHARS = 6


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
        DsDataErrorCodes.INVALID_DIGEST_CHARS: ("Digest must contain only alphanumeric characters (0-9, a-f)."),
        DsDataErrorCodes.INVALID_KEYTAG_SIZE: ("Enter a number between 0 and 65535."),
        DsDataErrorCodes.INVALID_KEYTAG_CHARS: ("Key tag must be numeric (0-9)."),
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
        SecurityEmailErrorCodes.BAD_DATA: ("Enter an email address in the required format, like name@example.com."),
    }

    def __init__(self, *args, code=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.code = code
        if self.code in self._error_mapping:
            self.message = self._error_mapping.get(self.code)

    def __str__(self):
        return f"{self.message}"


class APIError(Exception):
    """Custom exception for API-related errors"""

    pass
