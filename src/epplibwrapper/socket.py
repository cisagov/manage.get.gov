import logging
from time import sleep

try:
    from epplib import commands
    from epplib.client import Client
except ImportError:
    pass

from .errors import LoginError


logger = logging.getLogger(__name__)


class Socket:
    """Context manager which establishes a TCP connection with registry."""

    def __init__(self, client: Client, login: commands.Login) -> None:
        """Save the epplib client and login details."""
        self.client = client
        self.login = login

    def __enter__(self):
        """Runs connect(), which opens a connection with EPPLib."""
        self.connect()

    def __exit__(self, *args, **kwargs):
        """Runs disconnect(), which closes a connection with EPPLib."""
        self.disconnect()

    def connect(self):
        """Use epplib to connect."""
        logger.info("Opening socket on connection pool")
        self.client.connect()
        response = self.client.send(self.login)
        if self.is_login_error(response.code):
            self.client.close()
            raise LoginError(response.msg)
        return self.client

    def disconnect(self):
        """Close the connection."""
        logger.info("Closing socket on connection pool")
        try:
            self.client.send(commands.Logout())
            self.client.close()
        except Exception as err:
            logger.warning("Connection to registry was not cleanly closed.")
            logger.error(err)

    def send(self, command):
        """Sends a command to the registry.
        If the RegistryError code is >= 2000,
        then this function raises a LoginError.
        The calling function should handle this."""
        response = self.client.send(command)
        if self.is_login_error(response.code):
            self.client.close()
            raise LoginError(response.msg)

        return response

    def is_login_error(self, code):
        """Returns the result of code >= 2000 for RegistryError.
        This indicates that something weird happened on the Registry,
        and that we should return a LoginError."""
        return code >= 2000

    def test_connection_success(self):
        """Tests if a successful connection can be made with the registry.
        Tries 3 times."""
        # Something went wrong if this doesn't exist
        if not hasattr(self.client, "connect"):
            logger.warning("self.client does not have a connect attribute")
            return False

        counter = 0  # we'll try 3 times
        while True:
            try:
                self.client.connect()
                response = self.client.send(self.login)
            except (LoginError, OSError) as err:
                logger.error(err)
                should_retry = True
                if isinstance(err, LoginError):
                    should_retry = err.should_retry()
                if should_retry and counter < 10:
                    counter += 1
                    sleep((counter * 50) / 1000)  # sleep 50 ms to 150 ms
                else:  # don't try again
                    return False
            else:
                # If we encounter a login error, fail
                if self.is_login_error(response.code):
                    logger.warning("A login error was found in test_connection_success")
                    return False

                # Otherwise, just return true
                return True
            finally:
                self.disconnect()
