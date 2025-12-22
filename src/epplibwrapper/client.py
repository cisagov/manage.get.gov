"""Provide a wrapper around epplib to handle authentication and errors."""

import logging, time
from gevent.lock import BoundedSemaphore

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
        # set _client to None initially. In the event that the __init__ fails
        # before _client initializes, app should still start and be in a state
        # that it can attempt _client initialization on send attempts
        self._client = None  # type: ignore
        logger.info(f"=== REQUEST COUNT ===")
        self._waiting_count = 0  # Track how many requests are waiting
        # prepare (but do not send) a Login command
        self._login = commands.Login(
            cl_id=settings.SECRET_REGISTRY_CL_ID,
            password=settings.SECRET_REGISTRY_PASSWORD,
            obj_uris=[
                "urn:ietf:params:xml:ns:domain-1.0",
                "urn:ietf:params:xml:ns:contact-1.0",
            ],
        )
        # We should only ever have one active connection at a time
        self.connection_lock = BoundedSemaphore(1)

        self.connection_lock.acquire()
        try:
            self._initialize_client()
        except Exception:
            logger.warning("Unable to configure the connection to the registry.")
        finally:
            self.connection_lock.release()

    def _initialize_client(self) -> None:
        """Initialize a client, assuming _login defined. Sets _client to initialized
        client. Raises errors if initialization fails.
        This method will be called at app initialization, and also during retries."""
        # establish a client object with a TCP socket transport
        # note that type: ignore added in several places because linter complains
        # about _client initially being set to None, and None type doesn't match code
        self._client = Client(  # type: ignore
            SocketTransport(
                settings.SECRET_REGISTRY_HOSTNAME,
                cert_file=CERT.filename,
                key_file=KEY.filename,
                password=settings.SECRET_REGISTRY_KEY_PASSPHRASE,
            )
        )
        try:
            # use the _client object to connect
            self._connect()
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

    def _connect(self) -> None:
        """Connects to EPP. Sends a login command. If an invalid response is returned,
        the client will be closed and a LoginError raised."""
        self._client.connect()  # type: ignore
        response = self._client.send(self._login)  # type: ignore
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

        send_start = time.time()
        logger.info(f"=== STARTING {cmd_type} command to registry ===")

        try:
            # check for the condition that the _client was not initialized properly
            # at app initialization
            if self._client is None:
                self._initialize_client()

            registry_start = time.time()
            response = self._client.send(command)
            registry_elapsed = time.time() - registry_start
            logger.info(f"=== Registry responded to {cmd_type} in {registry_elapsed:.2f}s ===")
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
            send_elapsed = time.time() - send_start
            logger.info(f"=== Completed {cmd_type} in {send_elapsed:.2f}s total ===")

            if response.code >= 2000:
                raise RegistryError(response.msg, code=response.code, response=response)
            else:
                return response

    def _retry(self, command):
        """Retry sending a command through EPP by re-initializing the client
        and then sending the command."""
        # re-initialize by disconnecting and initial
        cmd_type = command.__class__.__name__

        logger.info(f"=== RETRY {cmd_type} command ===")

        self._disconnect()
        self._initialize_client()
        return self._send(command)

    def send(self, command, *, cleaned=False):
        """Login, the send the command. Retry once if an error is found"""
        # try to prevent use of this method without appropriate safeguards
        cmd_type = command.__class__.__name__
        logger.info(f"=== IN SEND FUNCTION ===")
        if not cleaned:
            raise ValueError("Please sanitize user input before sending it.")

        total_start = time.time()
        self._waiting_count += 1
        wait_position = self._waiting_count
        logger.info(f"=== EPP SEND START: {cmd_type} (queue position: {wait_position}) ===")
        logger.info(f"=== STARTING CONNECTION LOCK ===")

        lock_start = time.time()
        self.connection_lock.acquire()
        lock_wait = time.time() - lock_start

        logger.info(f"=== Lock acquired after {lock_wait:.2f}s wait time ===")
        if lock_wait > 5:
            logger.warning(f"!!! LONG !!! WAIT for lock: {lock_wait:.2f}s - CAUSE OF TIMEOUTS POSSIBLY???")

        try:
            result = self._send(command)
            total_elapsed = time.time() - total_start
            logger.info(
                f"=== EPP SEND COMMAND: {cmd_type} took {total_elapsed:.2f}s total (!waited {lock_wait:.2f}s for lock!) ==="
            )
            return result
        except RegistryError as err:
            if err.response:
                logger.info(f"cltrid is {err.response.cl_tr_id} svtrid is {err.response.sv_tr_id}")
            if (
                err.is_transport_error()
                or err.is_connection_error()
                or err.is_session_error()
                or err.is_server_error()
                or err.should_retry()
            ):
                message = f"{cmd_type} failed and will be retried"
                logger.info(f"{message} Error: {err}")
                result = self._retry(command)
                total_elapsed = time.time() - total_start
                logger.info(f"=== EPP SEND END (!after retry!): {cmd_type} took {total_elapsed:.2f}s total ===")
                return result
            else:
                raise err
        finally:
            self._waiting_count -= 1
            self.connection_lock.release()
            logger.info(f"=== LOCK RELEASED FOR {cmd_type} ===")


try:
    # Initialize epplib
    CLIENT = EPPLibWrapper()
    logger.info("registry client initialized")
except Exception:
    logger.warning("Unable to configure epplib. Registrar cannot contact registry.")
