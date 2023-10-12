import logging
from geventconnpool import ConnectionPool
from epplibwrapper.errors import RegistryError, LoginError
from epplibwrapper.socket import Socket

try:
    from epplib.commands import Hello
except ImportError:
    pass

logger = logging.getLogger(__name__)

class EppConnectionPool(ConnectionPool):
    def __init__(self, client, login, options):
        # For storing shared credentials
        self._client = client
        self._login = login
        super().__init__(**options)

    def _new_connection(self):
        socket = self.create_socket(self._client, self._login)
        try:
            connection = socket.connect()
            return connection
        except LoginError as err:
            message = "_new_connection failed to execute due to a registry login error."
            logger.error(message, exc_info=True)
            raise RegistryError(message) from err

    def _keepalive(self, c):
        """Sends a command to the server to keep the connection alive."""
        try:
            # Sends a ping to EPPLib
            c.send(Hello())
        except Exception as err:
            logger.error("Failed to keep the connection alive.", exc_info=True)
            raise RegistryError("Failed to keep the connection alive.") from err
    
    def create_socket(self, client, login) -> Socket:
        """Creates and returns a socket instance"""
        socket = Socket(client, login)
        return socket