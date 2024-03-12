"""Provide a wrapper around epplib to handle authentication and errors."""

import logging
import gevent
from gevent.lock import BoundedSemaphore
from collections import deque
from gevent.pool import Pool
from contextlib import contextmanager

try:
    from epplib.client import Client
    from epplib import commands
    from epplib.exceptions import TransportError, ParsingError
    from epplib.transport import SocketTransport
except ImportError:
    pass

from django.conf import settings

from .cert import Cert, Key
from .errors import ErrorCode, LoginError, PoolError, RegistryError

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

        # Create the pool, then populate it with connected clients.
        self.client_pool = Pool(self.pool_size)
        self.client_connection_pool_running = False

        # Lets store all threads in a common location.
        # Each thread contains a client with an active connection to EPP.
        self.client_threads = deque()

        # Keep track of every available connection
        self.connection_lock = BoundedSemaphore(self.pool_size)

        self.populate_client_pool()

    # == Pool Status == #
    def is_pool_running(self):
        """Returns a boolean indicating if the pool is currently running or not"""
        return self.client_connection_pool_running

    # == Pool == #
    def populate_client_pool(self):
        """
        Initializes or replenishes the client connection pool for EPP.

        First, it attempts to clear any existing connections by calling `kill_client_pool`.
        Then, it tries to create a new client pool with fresh connections. If an error occurs
        during pool creation (e.g., due to RegistryError), it attempts to clear any stale or
        partially initialized connections before either logging an error (if successful) or
        raising a PoolError if it cannot clean up existing connections. On successful creation,
        it sets self.client_connection_pool_running = True.
        """
        # Wipe the pool
        self.kill_client_pool()

        logger.info("populate_client_pool() -> Creating client pool")
        self.client_connection_pool_running = False
        try:
            self._create_client_pool()
        except PoolError as err:
            # Wipe the pool. We don't want anything sticking around.
            self.kill_client_pool()
            logger.error(f"populate_client_pool() -> Could not create client pool: {err}")
        except RegistryError as err:
            # Close old EPP connections if any exist. We want to start from a fresh slate.
            if len(self.client_pool) > 0:
                success = self.kill_client_pool()

            if success:
                logger.error(f"Cannot initialize the connection pool: {err}")
            else:
                logger.error("Existing connections could not be killed.")
        else:
            self.client_connection_pool_running = True

    def _create_client_pool(self):
        """Given our current pool size, add a thread containing an epp client with an open epp connection"""

        for _thread_number in range(self.pool_size):
            self._create_client_thread()

        # Wait for all the pools to finish spawning.
        self.client_pool.join(timeout=settings.EPP_POOL_TIMEOUT)

        # Check
        for thread_number, thread in enumerate(self.client_threads, start=1):
            if not thread.ready():
                raise PoolError("Not all client connections were initialized within the timeout period.")
            else:
                logger.info(f"populate_client_pool() -> Thread #{thread_number} created successfully.")

    def kill_client_pool(self) -> bool:
        """Destroys an existing client pool. Closes stale connections, then removes all gevent threads."""
        logger.warning("kill_client_pool() -> Killing client pool.")
        kill_was_successful = False
        try:
            # Remove stale connections
            logger.info(f"Closing stale connections")
            for client_thread in self.client_threads:
                # Get the underlying client object
                client = client_thread.value
                # Disconnect the client by sending a disconnect command to EPP.
                self._disconnect(client)

            # Remove all existing threads, clear self.client_threads, and reinit the pool
            self._cleanup_client_pool_and_threads()

            logger.info("kill_client_pool() -> Client pool cleared and all connections stopped.")
        except RegistryError as err:
            # If we run into a registry error, we can still cleanup dangling threads.
            logger.error(f"Could not disconnect all open connections. Closing active threads. Error: {err}")

            # Remove all existing threads, clear self.client_threads, and reinit the pool
            self._cleanup_client_pool_and_threads()
        except Exception as err:
            logger.error(f"kill_client_pool() -> An unspecified error occurred: {err}")
        else:
            kill_was_successful = True

        return kill_was_successful

    def _cleanup_client_pool_and_threads(self):
        """Removes all dangling threads in the client pool, and refreshes it."""

        # Kill all existing threads.
        logger.info(f"Killing all threads")
        self.client_pool.kill()

        # After killing all greenlets, clear the list to remove references.
        self.client_threads.clear()

        # Reinit the pool object itself, just for good measure
        self.client_pool = Pool(self.pool_size)

    # == Individual threads == #
    def _create_client_thread(self):
        """
        Spawns a new greenlet (thread) for initializing an EPP client connection.

        This method creates a new greenlet that runs `_initialize_client` to establish
        a new EPP client connection. The greenlet is then added to `self.client_threads`
        for tracking and management.
        """
        logger.debug(f"_create_client_thread() -> Creating a new thread")
        client_thread = self.client_pool.spawn(self._initialize_client)
        self.client_threads.append(client_thread)

    # == EPP Connection == #
    def _initialize_client(self) -> Client:
        """Initialize a client, assuming _login defined. Sets _client to initialized
        client. Raises errors if initialization fails.
        This method will be called at thread initialization, and also during retries."""
        logger.debug(f"In _initialize_client()")
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

        self.connection_lock.acquire()
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
        finally:
            self.connection_lock.release()

        return _client

    def _disconnect(self, client) -> None:
        """Close the connection."""
        try:
            client.send(commands.Logout())  # type: ignore
        except Exception as err:
            logger.warning(f"Logout command was not sent: {err}.")

        try:
            client.close()  # type: ignore
        except Exception as err:
            logger.warning(f"Connection to registry was not cleanly closed for client: {err}.")

    # == Send/Commands == #
    @contextmanager
    def get_active_client_connection(self):
        """
        Get a connection from the pool
        """
        if not self.client_threads or len(self.client_threads) == 0:
            self.populate_client_pool()

        self.connection_lock.acquire()
        thread = self.client_threads.popleft()
        try:
            client = thread.value
            yield client
        except RegistryError as err:
            raise err
        finally:
            logger.debug("get_active_client_connection() -> Releasing thread")
            self.connection_lock.release()
            self.client_threads.append(thread)

    def _send(self, command):
        """Helper function used by `send`."""
        cmd_type = command.__class__.__name__
        logger.debug("in _send()")
        try:
            with self.get_active_client_connection() as _client:
                if hasattr(_client, "send"):
                    response = _client.send(command)
                else:
                    # This can happen if get_active_client_connection is modifed
                    # and a thread is sent, rather than the underlying client.
                    # Or if the thread itself is none.
                    # This will not happen in normal code flow.
                    raise ValueError("_client does not have attribute 'send'")
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

    def send(self, command, *, cleaned=False):
        """Login, the send the command. Retry once if an error is found"""
        # try to prevent use of this method without appropriate safeguards
        cmd_type = command.__class__.__name__
        if not cleaned:
            raise ValueError("Please sanitize user input before sending it.")
        try:
            return self._send(command)
        except RegistryError as err:
            # Recreate the connection pool
            self.populate_client_pool()
            if err.should_restart_epp_client_and_retry():
                message = f"{cmd_type} failed and will be retried"
                logger.info(f"{message} Error: {err}")
                return self._send(command)
            else:
                raise err


try:
    # Initialize epplib
    CLIENT = EPPLibWrapper()
    logger.info("registry client initialized")
except Exception:
    logger.warning("Unable to configure epplib. Registrar cannot contact registry.")
