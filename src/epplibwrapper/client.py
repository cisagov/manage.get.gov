"""Provide a wrapper around epplib to handle authentication and errors."""

import logging
from time import sleep

try:
    from epplib.client import Client
    from epplib import commands
    from epplib.exceptions import TransportError, ParsingError
    from epplib.transport import SocketTransport
except ImportError:
    pass

from django.conf import settings

from .cert import Cert, Key
from .errors import LoginError, RegistryError
from .socket import Socket
from .utility.pool import EppConnectionPool

logger = logging.getLogger(__name__)

try:
    # Write cert and key to disk
    CERT = Cert()
    KEY = Key()
except Exception:
    CERT = None  # type: ignore
    KEY = None  # type: ignore
    logger.warning(
        "Problem with client certificate. Registrar cannot contact registry.",
        exc_info=True,
    )


class EPPLibWrapper:
    """
    A wrapper over epplib's client.

    ATTN: This should not be used directly. Use `Domain` from domain.py.
    """

    def __init__(self) -> None:
        """Initialize settings which will be used for all connections."""
        # prepare (but do not send) a Login command
        self._login = commands.Login(
            cl_id=settings.SECRET_REGISTRY_CL_ID,
            password=settings.SECRET_REGISTRY_PASSWORD,
            obj_uris=[
                "urn:ietf:params:xml:ns:domain-1.0",
                "urn:ietf:params:xml:ns:contact-1.0",
            ],
        )

        # establish a client object with a TCP socket transport
        self._client = Client(
            SocketTransport(
                settings.SECRET_REGISTRY_HOSTNAME,
                cert_file=CERT.filename,
                key_file=KEY.filename,
                password=settings.SECRET_REGISTRY_KEY_PASSPHRASE,
            )
        )
        options = {
            # Pool size
            "size": settings.EPP_CONNECTION_POOL_SIZE,
            # Which errors the pool should look out for
            "exc_classes": (
                LoginError,
                RegistryError,
            ),
            # Occasionally pings the registry to keep the connection alive
            "keepalive": settings.POOL_KEEP_ALIVE,
        }

        self._pool = None
        if not settings.DEBUG or self._test_registry_connection_success():
            self._pool = EppConnectionPool(
                client=self._client, login=self._login, options=options
            )
        else:
            logger.warning("Cannot contact the Registry")
            # TODO - signal that the app may need to restart?

    def _send(self, command):
        """Helper function used by `send`."""
        cmd_type = command.__class__.__name__
        try:
            if self._pool is None:
                raise LoginError
            # TODO - add a timeout
            with self._pool.get() as connection:
                response = connection.send(command)
        except (ValueError, ParsingError) as err:
            message = f"{cmd_type} failed to execute due to some syntax error."
            logger.warning(message, exc_info=True)
            raise RegistryError(message) from err
        except TransportError as err:
            message = f"{cmd_type} failed to execute due to a connection error."
            logger.warning(message, exc_info=True)
            raise RegistryError(message) from err
        except LoginError as err:
            # For linter
            text = "failed to execute due to a registry login error."
            message = f"{cmd_type} {text}"
            logger.warning(message, exc_info=True)
            raise RegistryError(message) from err
        except Exception as err:
            message = f"{cmd_type} failed to execute due to an unknown error."
            logger.warning(message, exc_info=True)
            raise RegistryError(message) from err
        else:
            if response.code >= 2000:
                raise RegistryError(response.msg, code=response.code)
            else:
                return response

    def send(self, command, *, cleaned=False):
        """Login, send the command, then close the connection. Tries 3 times."""
        # try to prevent use of this method without appropriate safeguards
        if not cleaned:
            raise ValueError("Please sanitize user input before sending it.")

        counter = 0  # we'll try 3 times
        while True:
            try:
                return self._send(command)
            except RegistryError as err:
                if err.should_retry() and counter < 3:
                    counter += 1
                    sleep((counter * 50) / 1000)  # sleep 50 ms to 150 ms
                else:  # don't try again
                    raise err

    def _test_registry_connection_success(self):
        """Check that determines if our login
        credentials are valid, and/or if the Registrar
        can be contacted
        """
        socket = Socket(self._login, self._client)
        can_login = False
        # Something went wrong if this doesn't exist
        if hasattr(socket, "test_connection_success"):
            can_login = socket.test_connection_success()
        return can_login


try:
    # Initialize epplib
    CLIENT = EPPLibWrapper()
    logger.debug("registry client initialized")
except Exception:
    CLIENT = None  # type: ignore
    logger.warning(
        "Unable to configure epplib. Registrar cannot contact registry.", exc_info=True
    )
