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
from .errors import ErrorCode, LoginError, RegistryError
from .utility.pool import PoolExhausted, EPPConnectionPool

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
        # this will immediately kick off the maintenance loop
        self._pool = EPPConnectionPool(connection_factory=self._create_connection,
                        size=settings.EPP_CONNECTION_POOL_SIZE,
                        borrow_timeout=settings.EPP_POOL_BORROW_TIMEOUT,
                        idle_ping_seconds=settings.EPP_POOL_IDLE_PING_SECONDS,
                        heartbeat_interval=settings.EPP_POOL_HEARTBEAT_INTERVAL,)

    def _create_connection(self) -> "Client":
        """Initialize a client, assuming _login defined. Raises errors if initialization fails.
        This method will be called at app initialization, when the pool makes a new conneciton,
        and upon retries if a connection is discarded or retired."""
        # establish a client object with a TCP socket transport

        client = Client(  # type: ignore
            SocketTransport(
                settings.SECRET_REGISTRY_HOSTNAME,
                cert_file=CERT.filename,
                key_file=KEY.filename,
                password=settings.SECRET_REGISTRY_KEY_PASSPHRASE,
            )
        )
        try:
            self._connect(client=client)
        except TransportError as err:
            message = "_create_connection failed to execute due to a connection error."
            logger.error(f"{message} Error: {err}")
            raise RegistryError(message, code=ErrorCode.TRANSPORT_ERROR) from err
        except LoginError as err:
            raise err
        except Exception as err:
            message = "_create_connection failed to execute due to an unknown error."
            logger.error(f"{message} Error: {err}")
            raise RegistryError(message) from err
        
        # Client is stored as a connection inside the pool
        return client

    def _connect(self, client: "Client") -> None:
        """Connects to EPP. Sends a login command. If an invalid response is returned,
        the client will be closed and a LoginError raised."""
        client.connect()  # type: ignore
        
        # Note this doesn't use the "with" setup as then client would close after the send
        # we want to keep the connection open
        response = client.send(self._login)  # type: ignore
        if response.code >= 2000:  # type: ignore / this is the failure code
            try:
                client.close()  # type: ignore
            except Exception:
                pass # We don't care if this fails to close, as the connection wasn't fully completed
                    # due to login failing
            raise LoginError(response.msg)  # type: ignore


    def _send(self, command):
        """Helper function used by `send` handles the actual sending of a message
        this utilizes the pool to get a connection and automatically closes the connection
        when done (indirectly via the with statement).
        
        Does NOT contain retry logic
        
        Raises RegistryError

        Returns epplib response object
        """
        cmd_type = command.__class__.__name__

        try:
           # Grab a connection from the pool. Connection is automagically
           # put back into the Q once the with finishes
            with self._pool.connection() as clientConnection:
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
        except RegistryError:
            # _create_connection is called by the "self._pool.connection() as clientConnection"
            # This can result in a registry error. Raising it again here allows for retry    
            raise
        except Exception as err:
            message = f"{cmd_type} failed to execute due to an unknown error."
            logger.error(f"{message} Error: {err}")
            raise RegistryError(message) from err
        
        else:
            if response.code >= 2000:
                raise RegistryError(response.msg, code=response.code, response=response)
            else:
                return response


    def send(self, command):
        """Login, the send the command. Retry three times if an error is found."""
        # try to prevent use of this method without appropriate safeguards
        cmd_type = command.__class__.__name__
        
        max_attempts =4
        for attempt in range (1, max_attempts+1):
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
                ) and attempt <max_attempts:
                    message = f"{cmd_type} failed and will be retried"
                    logger.info(f"{message} Error: {err}")
                 
                    sleep((attempt *50)/1000) # sleep 50-150ms incase a logout error occured
                else:
                    raise err


try:
    # Initialize epplib
    CLIENT = EPPLibWrapper()
    logger.info("registry client initialized")
except Exception:
    logger.warning("Unable to configure epplib. Registrar cannot contact registry.")
