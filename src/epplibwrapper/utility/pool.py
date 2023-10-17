import logging
import gevent
from geventconnpool import ConnectionPool
from epplibwrapper.socket import Socket
from epplibwrapper.utility.pool_error import PoolError, PoolErrorCodes
try:
    from epplib.commands import Hello
except ImportError:
    pass


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
        super().__init__(**options)

    def _new_connection(self):
        socket = self._create_socket(self._client, self._login)
        try:
            connection = socket.connect()
            return connection
        except Exception as err:
            message = f"Failed to execute due to a registry login error: {err}"
            logger.error(message, exc_info=True)
            # We want to raise a pool error rather than a LoginError here
            # because if this occurs internally, we should handle this
            # differently than we otherwise would for LoginError.
            raise PoolError(code=PoolErrorCodes.NEW_CONNECTION_FAILED) from err

    def _keepalive(self, c):
        """Sends a command to the server to keep the connection alive."""
        try:
            # Sends a ping to EPPLib
            c.send(Hello())
        except Exception as err:
            message = "Failed to keep the connection alive."
            logger.error(message, exc_info=True)
            raise PoolError(code=PoolErrorCodes.KEEP_ALIVE_FAILED) from err

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
            gevent.killall(self.conn)
            self.conn.clear()
            # Clear the semaphore
            for i in range(self.lock.counter):
                self.lock.release()
        except Exception as err:
            logger.error("Could not kill all connections.")
            raise err

    def repopulate_all_connections(self):
        """Regenerates the connection pool.
        If any connections exist, kill them first.
        """
        if len(self.conn) > 0:
            self.kill_all_connections()
        for i in range(self.size):
            self.lock.acquire()
        for i in range(self.size):
            gevent.spawn_later(self.SPAWN_FREQUENCY * i, self._addOne)
