import logging
from geventconnpool import ConnectionPool
from epplibwrapper import RegistryError
from epplibwrapper.errors import LoginError
from epplibwrapper.socket import Socket

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
            logger.warning(message, exc_info=True)
            raise RegistryError(message) from err

    def _keepalive(self, connection):
        pass
    
    def create_socket(self, client, login) -> Socket:
        """Creates and returns a socket instance"""
        socket = Socket(client, login)
        return socket