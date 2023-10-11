"""Provide a wrapper around epplib to handle authentication and errors."""

import logging
from time import sleep

from epplibwrapper.utility.pool import EppConnectionPool

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
        # prepare a context manager which will connect and login when invoked
        # (it will also logout and disconnect when the context manager exits)
        self._connect = Socket(self._client, self._login)
        options = {
            # Pool size
            "size": 10,
            # Which errors the pool should look out for
            "exc_classes": (LoginError, RegistryError,),
            # Should we ping the connection on occassion to keep it alive?
            "keepalive": None,
        }
        self._pool = EppConnectionPool(client=self._client, login=self._login, options=options)

    def _send(self, command):
        """Helper function used by `send`."""
        try:
            cmd_type = command.__class__.__name__
            with self._pool.get() as connection:
                response = connection.send(command)
        except (ValueError, ParsingError) as err:
            message = "%s failed to execute due to some syntax error."
            logger.warning(message, cmd_type, exc_info=True)
            raise RegistryError(message) from err
        except TransportError as err:
            message = "%s failed to execute due to a connection error."
            logger.warning(message, cmd_type, exc_info=True)
            raise RegistryError(message) from err
        except LoginError as err:
            message = "%s failed to execute due to a registry login error."
            logger.warning(message, cmd_type, exc_info=True)
            raise RegistryError(message) from err
        except Exception as err:
            message = "%s failed to execute due to an unknown error." % err
            logger.warning(message, cmd_type, exc_info=True)
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


try:
    # Initialize epplib
    CLIENT = EPPLibWrapper()
    logger.debug("registry client initialized")
except Exception:
    CLIENT = None  # type: ignore
    logger.warning(
        "Unable to configure epplib. Registrar cannot contact registry.", exc_info=True
    )
