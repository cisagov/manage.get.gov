import time
import logging
from socketpool import Connector
try:
    from epplib.exceptions import TransportError, ParsingError
except ImportError:
    pass
from ..errors import LoginError, RegistryError

from epplibwrapper.socket import Socket

logger = logging.getLogger(__name__)

class EPPConnector(Connector):
    def __init__(self, client, login, backend_mod, pool=None):
        self._connected = True
        self._life = time.time()
        self._pool = pool

        self.backend_mod = backend_mod
        self._socket = Socket(client, login)
        self._socket.connect()

    def __del__(self):
        self.release()

    def matches(self, **match_options):
        return True

    def is_connected(self):
        return self._connected

    def handle_exception(self, exception):
        logger.error(exception)

    def get_lifetime(self):
        return self._life

    def invalidate(self):
        self._socket.disconnect()
        self._connected = False
        self._life = -1

    def release(self):
        if self._pool is not None:
            if self._connected:
                self._pool.release_connection(self)
            else:
                self._pool = None

    def send(self, command):
        try:
            cmd_type = command.__class__.__name__
            response = self._socket.send(command)
        except (ValueError, ParsingError) as err:
            message = "%s failed to execute due to some syntax error."
            logger.warning(message, cmd_type, exc_info=True)
            raise RegistryError(message) from err
        except TransportError as err:
            message = "%s failed to execute due to a connection error."
            logger.warning(message, cmd_type, exc_info=True)
            raise RegistryError(message) from err
        except LoginError as err:
            message = "%s failed to execute due to a registry login error."
            logger.warning(message, cmd_type, exc_info=True)
            raise RegistryError(message) from err
        except Exception as err:
            message = "%s failed to execute due to an unknown error." % err
            logger.warning(message, cmd_type, exc_info=True)
            raise RegistryError(message) from err
        else:
            if response.code >= 2000:
                raise RegistryError(response.msg, code=response.code)
            else:
                return response
