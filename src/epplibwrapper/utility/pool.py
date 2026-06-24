import logging
from typing import List
import gevent
from geventconnpool import ConnectionPool
from epplibwrapper.socket import Socket
from epplibwrapper.utility.pool_error import PoolError, PoolErrorCodes

try:
    from epplib.commands import Hello
    from epplib.exceptions import TransportError
except ImportError:
    pass

from gevent.lock import BoundedSemaphore
from collections import deque

logger = logging.getLogger(__name__)


class EPPConnectionPool(ConnectionPool):
    """A connection pool for EPPLib.

    Args:
        client (Client): The client
        login (commands.Login): Login creds
        options (dict): Options for the ConnectionPool
        base class
    """

    def __init__(self, client, login, options: dict):
        # For storing shared credentials
        self._client = client
        self._login = login

        # Keep track of each greenlet
        self.greenlets: List[gevent.Greenlet] = []

        # Define optional pool settings.
        # Kept in a dict so that the parent class,
        # client.py, can maintain seperation/expandability
        self.size = 1
        if "size" in options:
            self.size = options["size"]

        self.exc_classes = tuple((TransportError,))
        if "exc_classes" in options:
            self.exc_classes = options["exc_classes"]

        self.keepalive = None
        if "keepalive" in options:
            self.keepalive = options["keepalive"]

        # Determines the period in which new
        # gevent threads are spun up.
        # This time period is in seconds. So for instance, .1 would be .1 seconds.
        self.spawn_frequency = 0.1
        if "spawn_frequency" in options:
            self.spawn_frequency = options["spawn_frequency"]

        self.conn: deque = deque()
        self.lock = BoundedSemaphore(self.size)

        self.populate_all_connections()

    def _new_connection(self):
        socket = self._create_socket(self._client, self._login)
        try:
            connection = socket.connect()
            return connection
        except Exception as err:
            message = f"Failed to execute due to a registry error: {err}"
            logger.error(message, exc_info=True)
            # We want to raise a pool error rather than a LoginError here
            # because if this occurs internally, we should handle this
            # differently than we otherwise would for LoginError.
            raise PoolError(code=PoolErrorCodes.NEW_CONNECTION_FAILED) from err

    def _keepalive(self, c):
        """Sends a command to the server to keep the connection alive."""
        try:
            # Sends a ping to the registry via EPPLib
            c.send(Hello())
        except Exception as err:
            message = "Failed to keep the connection alive."
            logger.error(message, exc_info=True)
            raise PoolError(code=PoolErrorCodes.KEEP_ALIVE_FAILED) from err

    def _keepalive_periodic(self):
        """Overriding _keepalive_periodic from geventconnpool so that PoolErrors
        are properly handled, as opposed to printing to stdout"""
        delay = float(self.keepalive) / self.size
        while 1:
            try:
                with self.get() as c:
                    self._keepalive(c)
            except PoolError as err:
                logger.error(err.message, exc_info=True)
            except self.exc_classes:
                # Nothing to do, the pool will generate a new connection later
                pass
            gevent.sleep(delay)

    def _create_socket(self, client, login) -> Socket:
        """Creates and returns a socket instance"""
        socket = Socket(client, login)
        return socket

    def get_connections(self):
        """Returns the connection queue"""
        return self.conn

    def kill_all_connections(self):
        """Kills all active connections in the pool."""
        try:
            if len(self.conn) > 0 or len(self.greenlets) > 0:
                logger.info("Attempting to kill connections")
                gevent.killall(self.greenlets)

                self.greenlets.clear()
                for connection in self.conn:
                    connection.disconnect()
                self.conn.clear()

                # Clear the semaphore
                self.lock = BoundedSemaphore(self.size)
                logger.info("Finished killing connections")
            else:
                logger.info("No connections to kill.")
        except Exception as err:
            logger.error("Could not kill all connections.")
            raise PoolError(code=PoolErrorCodes.KILL_ALL_FAILED) from err

    def populate_all_connections(self):
        """Generates the connection pool.
        If any connections exist, kill them first.
        Based off of the __init__ definition for geventconnpool.
        """
        if len(self.conn) > 0 or len(self.greenlets) > 0:
            self.kill_all_connections()

        # Setup the lock
        for i in range(self.size):
            self.lock.acquire()

        # Open multiple connections
        for i in range(self.size):
            self.greenlets.append(gevent.spawn_later(self.spawn_frequency * i, self._addOne))

        # Open a "keepalive" thread if we want to ping open connections
        if self.keepalive:
            self.greenlets.append(gevent.spawn(self._keepalive_periodic))
