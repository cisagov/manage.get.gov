"""Provide a wrapper around epplib to handle authentication and errors."""

import logging
from time import sleep

from gevent import Timeout

from epplibwrapper.utility.pool_status import PoolStatus

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
from .utility.pool import EPPConnectionPool

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

    def __init__(self, start_connection_pool=True) -> None:
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

        self.pool_options = {
            # Pool size
            "size": settings.EPP_CONNECTION_POOL_SIZE,
            # Which errors the pool should look out for
            "exc_classes": (TransportError,),
            # Occasionally pings the registry to keep the connection alive.
            # Value in seconds => (keepalive / size)
            "keepalive": settings.POOL_KEEP_ALIVE,
        }

        self._pool = None
        # Tracks the status of the pool
        self.pool_status = PoolStatus()

        if start_connection_pool:
            self.start_connection_pool()

    def _send(self, command):
        """Helper function used by `send`."""
        cmd_type = command.__class__.__name__
        # Start a timeout to check if the pool is hanging
        timeout = Timeout(settings.POOL_TIMEOUT)
        timeout.start()
        try:
            if not self.pool_status.connection_success:
                raise LoginError(
                    "Couldn't connect to the registry after three attempts"
                )
            with self._pool.get() as connection:
                response = connection.send(command)
        except Timeout as t:
            if t is timeout:
                # Flag that the pool is frozen,
                # then restart the pool.
                self.pool_status.pool_hanging = True
                self.start_connection_pool()
        except (ValueError, ParsingError) as err:
            message = f"{cmd_type} failed to execute due to some syntax error."
            logger.error(message, exc_info=True)
            raise RegistryError(message) from err
        except TransportError as err:
            message = f"{cmd_type} failed to execute due to a connection error."
            logger.error(message, exc_info=True)
            raise RegistryError(message) from err
        except LoginError as err:
            # For linter
            text = "failed to execute due to a registry login error."
            message = f"{cmd_type} {text}"
            logger.error(message, exc_info=True)
            raise RegistryError(message) from err
        except Exception as err:
            message = f"{cmd_type} failed to execute due to an unknown error."
            logger.error(message, exc_info=True)
            raise RegistryError(message) from err
        else:
            print(f"test thing {response}")
            if response.code >= 2000:
                raise RegistryError(response.msg, code=response.code)
            else:
                return response
        finally:
            timeout.close()

    def send(self, command, *, cleaned=False):
        """Login, send the command, then close the connection. Tries 3 times."""
        # try to prevent use of this method without appropriate safeguards
        if not cleaned:
            raise ValueError("Please sanitize user input before sending it.")

        # Reopen the pool if its closed
        # Only occurs when a login error is raised, after connection is successful
        if not self.pool_status.pool_running:
            # We want to reopen the connection pool,
            # but we don't want the end user to wait while it opens.
            # Raise syntax doesn't allow this, so we use a try/catch
            # block.
            try:
                logger.error("Can't contact the Registry. Pool was not running.")
                raise RegistryError("Can't contact the Registry. Pool was not running.")
            except RegistryError as err:
                raise err
            finally:
                self.start_connection_pool()

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

    def get_pool(self):
        """Get the current pool instance"""
        return self._pool
    
    def _create_pool(self, client, login, options):
        """Creates and returns new pool instance"""
        return EPPConnectionPool(
                client, login, options
        )

    def start_connection_pool(
        self, restart_pool_if_exists=True, try_start_if_invalid=False
    ):
        """Starts a connection pool for the registry.

        restart_pool_if_exists -> bool:
        If an instance of the pool already exists,
        then then that instance will be killed first.
        It is generally recommended to keep this enabled.

        try_start_if_invalid -> bool:
        Designed for use in test cases, if we can't connect
        to the registry, ignore that and try to connect anyway
        It is generally recommended to keep this disabled.
        """
        # Since we reuse the same creds for each pool, we can test on
        # one socket, and if successful, then we know we can connect.
        if (
            not try_start_if_invalid
            and settings.DEBUG
            or not self._test_registry_connection_success()
        ):
            logger.warning("Cannot contact the Registry")
            self.pool_status.connection_success = False
        else:
            self.pool_status.connection_success = True

            # If this function is reinvoked, then ensure
            # that we don't have duplicate data sitting around.
            if self._pool is not None and restart_pool_if_exists:
                logger.info("Connection pool restarting...")
                self.kill_pool()

            self._pool = self._create_pool(
                self._client, self._login, self.pool_options
            ) 

            self.pool_status.pool_running = True
            self.pool_status.pool_hanging = False

            logger.info("Connection pool started")

    def kill_pool(self):
        """Kills the existing pool. Use this instead
        of self._pool = None, as that doesn't clear
        gevent instances."""
        if self._pool is not None:
            self._pool.kill_all_connections()
            self._pool = None
            self.pool_status.pool_running = False
            return
        logger.info("kill_pool() was invoked but there was no pool to delete")

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
    logger.info("registry client initialized")
except Exception:
    CLIENT = None  # type: ignore
    logger.warning(
        "Unable to configure epplib. Registrar cannot contact registry.", exc_info=True
    )
