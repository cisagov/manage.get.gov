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

    def _send(self, command):
        """Helper function used by `send`."""
        try:
            with self._connect as wire:
                response = wire.send(command)
        except (ValueError, ParsingError) as err:
            logger.warning(
                "%s failed to execute due to some syntax error."
                % command.__class__.__name__,
                exc_info=True,
            )
            raise RegistryError() from err
        except TransportError as err:
            logger.warning(
                "%s failed to execute due to a connection error."
                % command.__class__.__name__,
                exc_info=True,
            )
            raise RegistryError() from err
        except LoginError as err:
            logger.warning(
                "%s failed to execute due to a registry login error."
                % command.__class__.__name__,
                exc_info=True,
            )
            raise RegistryError() from err
        except Exception as err:
            logger.warning(
                "%s failed to execute due to an unknown error."
                % command.__class__.__name__,
                exc_info=True,
            )
            raise RegistryError() from err
        else:
            if response.code >= 2000:
                raise RegistryError(response.msg)
            else:
                return response

    def send(self, command):
        """Login, send the command, then close the connection. Tries 3 times."""
        counter = 0  # we'll try 3 times
        while True:
            try:
                return self._send(command)
            except RegistryError as err:
                if counter == 3:  # don't try again
                    raise err
                else:
                    counter += 1
                    sleep((counter * 50) / 1000)  # sleep 50 ms to 150 ms


try:
    # Initialize epplib
    CLIENT = EPPLibWrapper()
    logger.debug("registry client initialized")
except Exception:
    CLIENT = None  # type: ignore
    logger.warning(
        "Unable to configure epplib. Registrar cannot contact registry.", exc_info=True
    )
