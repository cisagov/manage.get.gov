from geventconnpool import ConnectionPool
from epplibwrapper.socket import Socket

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
        except Exception as err:
            raise err

    def _keepalive(self, connection):
        pass
    
    def create_socket(self, client, login) -> Socket:
        """Creates and returns a socket instance"""
        socket = Socket(client, login)
        return socket