from oic import rndstr
from http import HTTPStatus as status


class OIDCException(Exception):
    """
    Base class for django oidc exceptions.
    Subclasses should provide `.status` and `.friendly_message` properties.
    `.locator`, if used, should be a useful, unique identifier for
    locating related log messages.
    """

    status = status.INTERNAL_SERVER_ERROR
    friendly_message = "A server error occurred."
    locator = None

    def __init__(self, friendly_message=None, status=None, locator=None):
        if friendly_message is not None:
            self.friendly_message = friendly_message
        if status is not None:
            self.status = status
        if locator is not None:
            self.locator = locator
        else:
            self.locator = rndstr(size=12)

    def __str__(self):
        return f"[{self.locator}] {self.friendly_message}"


class AuthenticationFailed(OIDCException):
    status = status.UNAUTHORIZED
    friendly_message = "This login attempt didn't work."


class InternalError(OIDCException):
    status = status.INTERNAL_SERVER_ERROR
    friendly_message = "The system broke while trying to log you in."


class BannedUser(AuthenticationFailed):
    friendly_message = "Your user is not valid in this application."
