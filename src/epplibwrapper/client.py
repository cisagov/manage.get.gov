"""Provide a wrapper around epplib to handle authentication and errors."""

import logging
from time import sleep


try:
    from epplib.client import Client
    from epplib import commands
    from epplib.exceptions import TransportError, ParsingError
    from epplib.transport import SocketTransport
    from utility.pool import PooledConnection, PoolExhausted, EPPConnectionPool
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
   
        # prepare (but do not send) a Login command
        self._login = commands.Login(
            cl_id=settings.SECRET_REGISTRY_CL_ID,
            password=settings.SECRET_REGISTRY_PASSWORD,
            obj_uris=[
                "urn:ietf:params:xml:ns:domain-1.0",
                "urn:ietf:params:xml:ns:contact-1.0",
            ],
        )
        # Create the pool
        # this will immediately kick off the maintanence loop
        self._pool = EPPConnectionPool(connection_factory=self._create_connection,
                        size=settings.EPP_CONNECTION_POOL_SIZE,
                        checkout_timeout=settings.EPP_POOL_borrow_TIMEOUT,
                        idle_ping_seconds=settings.EPP_POOL_IDLE_PING_SECONDS,
                        heartbeat_interval=settings.EPP_POOL_HEARTBEAT_INTERVAL,
                        idle_max_seconds=settings.EPP_POOL_IDLE_MAX_SECONDS,)
        
      

        
        

    def _create_connection(self) -> None:
        """Initialize a client, assuming _login defined. Sets _client to initialized
        client. Raises errors if initialization fails.
        This method will be called at app initialization, and also during retries."""
        # establish a client object with a TCP socket transport
        # note that type: ignore added in several places because linter complains
        # about _client initially being set to None, and None type doesn't match code
        client = Client(  # type: ignore
            SocketTransport(
                settings.SECRET_REGISTRY_HOSTNAME,
                cert_file=CERT.filename,
                key_file=KEY.filename,
                password=settings.SECRET_REGISTRY_KEY_PASSPHRASE,
            )
        )
        try:
            # use the _client object to connect
            self._connect(client=client)
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
        
        # Client is stored as a connection inside the pool
        return client

    def _connect(self, client: Client) -> None:
        """Connects to EPP. Sends a login command. If an invalid response is returned,
        the client will be closed and a LoginError raised."""
        client.connect()  # type: ignore
        response = client.send(self._login)  # type: ignore
        if response.code >= 2000:  # type: ignore
            self._client.close()  # type: ignore
            raise LoginError(response.msg)  # type: ignore

    def _disconnect(self) -> None:
        """Close the connection. Sends a logout command and closes the connection."""
        self._send_logout_command()
        self._close_client()

    def _send_logout_command(self):
        """Sends a logout command to epp"""
        try:
            self._client.send(commands.Logout())  # type: ignore
        except Exception as err:
            logger.warning(f"Logout command not sent successfully: {err}")

    def _close_client(self):
        """Closes an active client connection"""
        try:
            self._client.close()
        except Exception as err:
            logger.warning(f"Connection to registry was not cleanly closed: {err}")

    def _send(self, command):
        """Helper function used by `send`."""
        cmd_type = command.__class__.__name__

        try:
           # Grab a connection from the pool. Connection is automagically
           # put back into the Q once the with finishes
            with self._pool.connection() as clientConnection:
                # TODO - initialize client here if not?????
                response = clientConnection.send(command)
        except PoolExhausted as err:
            # Every connection stayed checked out for the whole wait.
            # The registry/socket may be fine - this is a capacity signal.
            message = f"{cmd_type} failed: all pooled EPP connections are busy."
            logger.error(f"{message} Error: {err}. Pool stats: {self._pool.stats()}", exc_info=True)
            raise RegistryError(message) from err
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
                raise RegistryError(response.msg, code=response.code, response=response)
            else:
                return response


    def send(self, command, *, cleaned=False):
        """Login, the send the command. Retry once if an error is found"""
        # try to prevent use of this method without appropriate safeguards
        cmd_type = command.__class__.__name__
        if not cleaned:
            raise ValueError("Please sanitize user input before sending it.")

        counter=0
        try:
            return self._send(command)
        except RegistryError as err:
            if err.response:
                logger.info(f"cltrid is {err.response.cl_tr_id} svtrid is {err.response.sv_tr_id}")
            if (
                err.is_transport_error()
                or err.is_connection_error()
                or err.is_session_error()
                or err.is_server_error()
                or err.should_retry()
            ) and counter <3:
                message = f"{cmd_type} failed and will be retried"
                logger.info(f"{message} Error: {err}")
                counter+=1
                sleep((counter *50)/1000) # sleep 50-150ms incase a logout error occured
            else:
                raise err


try:
    # Initialize epplib
    CLIENT = EPPLibWrapper()
    logger.info("registry client initialized")
except Exception:
    logger.warning("Unable to configure epplib. Registrar cannot contact registry.")
