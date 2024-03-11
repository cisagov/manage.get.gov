"""Provide a wrapper around epplib to handle authentication and errors."""

import logging
import gevent
from gevent.lock import BoundedSemaphore
from collections import deque
from gevent.pool import Pool

try:
    from epplib.client import Client
    from epplib import commands
    from epplib.exceptions import TransportError, ParsingError
    from epplib.transport import SocketTransport
except ImportError:
    pass

from django.conf import settings

from .cert import Cert, Key
from .errors import ErrorCode, LoginError, RegistryError

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
        # Create a container for the login command
        self._login = commands.Login(
            cl_id=settings.SECRET_REGISTRY_CL_ID,
            password=settings.SECRET_REGISTRY_PASSWORD,
            obj_uris=[
                "urn:ietf:params:xml:ns:domain-1.0",
                "urn:ietf:params:xml:ns:contact-1.0",
            ],
        )

        self.pool_size = settings.EPP_CONNECTION_POOL_SIZE

        # Lets store all threads in a common location. 
        # Each thread contains a client with an active connection to EPP.
        self.client_threads = []

        # Create the pool, then populate it with connected clients.
        self.client_pool = Pool(self.pool_size)
        self.connection_pool_started = False

        try:
            self.populate_client_pool()
        except RegistryError as err:
            logger.error(f"Cannot initialize the connection pool: {err}")
        else:
            self.connection_pool_started = True


    def populate_client_pool(self):
        """Given our current pool size, add a thread containing an epp client with an open epp connection"""
        for _thread_number in range(self.pool_size):
            client_thread = self.client_pool.spawn(self._initialize_client)
            self.client_threads.append(client_thread)

        # Wait for all the pools to finish spawning.
        self.client_pool.join(timeout=settings.EPP_POOL_TIMEOUT)

        for thread_number, thread in enumerate(self.client_threads, start=1):
            # TODO: Throw some error
            if not thread.ready():
                # TODO: Rather than raise an error, maybe we can just reduce the pool size dynamically?
                raise RegistryError("Not all client connections were initialized within the timeout period.")
            else:
                logger.info(f"populate_client_pool() -> Thread #{thread_number} created successfully.")

    def _initialize_client(self) -> Client:
        """Initialize a client, assuming _login defined. Sets _client to initialized
        client. Raises errors if initialization fails.
        This method will be called at app initialization, and also during retries."""
        # establish a client object with a TCP socket transport
        # note that type: ignore added in several places because linter complains
        # about _client initially being set to None, and None type doesn't match code
        _client = Client(  # type: ignore
            SocketTransport(
                settings.SECRET_REGISTRY_HOSTNAME,
                cert_file=CERT.filename,
                key_file=KEY.filename,
                password=settings.SECRET_REGISTRY_KEY_PASSPHRASE,
            )
        )
        try:
            # use the _client object to connect
            _client.connect()  # type: ignore
            response = _client.send(self._login)  # type: ignore
            if response.code >= 2000:  # type: ignore
                _client.close()  # type: ignore
                raise LoginError(response.msg)  # type: ignore
        except TransportError as err:
            message = "_initialize_client failed to execute due to a connection error."
            logger.error(f"{message} Error: {err}")
            raise RegistryError(message, code=ErrorCode.TRANSPORT_ERROR) from err
        except LoginError as err:
            raise err
        except Exception as err:
            message = "_initialize_client failed to execute due to an unknown error."
            logger.error(f"{message} Error: {err}")
            raise RegistryError(message) from err
        
        return _client

    def _disconnect(self, client) -> None:
        """Close the connection."""
        try:
            client.send(commands.Logout())  # type: ignore
            client.close()  # type: ignore
        except Exception:
            logger.warning("Connection to registry was not cleanly closed.")

    def _send(self, command):
        """Helper function used by `send`."""
        cmd_type = command.__class__.__name__

        try:
            _client = self._initialize_client()
            response = _client.send(command)
        except (ValueError, ParsingError) as err:
            message = f"{cmd_type} failed to execute due to some syntax error."
            logger.error(f"{message} Error: {err}")
            raise RegistryError(message) from err
        except TransportError as err:
            message = f"{cmd_type} failed to execute due to a connection error."
            logger.error(f"{message} Error: {err}")
            raise RegistryError(message, code=ErrorCode.TRANSPORT_ERROR) from err
        except LoginError as err:
            # For linter due to it not liking this line length
            text = "failed to execute due to a registry login error."
            message = f"{cmd_type} {text}"
            logger.error(f"{message} Error: {err}")
            raise RegistryError(message) from err
        except Exception as err:
            message = f"{cmd_type} failed to execute due to an unknown error."
            logger.error(f"{message} Error: {err}")
            raise RegistryError(message) from err
        else:
            if response.code >= 2000:
                raise RegistryError(response.msg, code=response.code)
            else:
                return response

    def _retry(self, client, command):
        """Retry sending a command through EPP by re-initializing the client
        and then sending the command."""
        # re-initialize by disconnecting and initial
        self._disconnect(client)
        return self._send(command)

    def send(self, command, *, cleaned=False):
        """Login, the send the command. Retry once if an error is found"""
        # try to prevent use of this method without appropriate safeguards
        cmd_type = command.__class__.__name__
        if not cleaned:
            raise ValueError("Please sanitize user input before sending it.")
        try:
            return self._send(command)
        except RegistryError as err:
            if (
                err.is_transport_error()
                or err.is_connection_error()
                or err.is_session_error()
                or err.is_server_error()
                or err.should_retry()
            ):
                message = f"{cmd_type} failed and will be retried"
                logger.info(f"{message} Error: {err}")
                return self._retry(command)
            else:
                raise err


try:
    # Initialize epplib
    CLIENT = EPPLibWrapper()
    logger.info("registry client initialized")
except Exception:
    logger.warning("Unable to configure epplib. Registrar cannot contact registry.")
