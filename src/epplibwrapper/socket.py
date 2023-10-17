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
        self.client.connect()
        response = self.client.send(self.login)
        if self.is_login_error(response.code):
            self.client.close()
            raise LoginError(response.msg)
        return self.client

    def is_login_error(self, code):
        return code >= 2000

    def test_connection_success(self):
        """Tests if a successful connection can be made with the registry.
        Tries 3 times"""
        # Something went wrong if this doesn't exist
        if not hasattr(self.client, "connect"):
            return False

        counter = 0  # we'll try 3 times
        while True:
            try:
                self.client.connect()
                response = self.client.send(self.login)
            except LoginError as err:
                if err.should_retry() and counter < 3:
                    counter += 1
                    sleep((counter * 50) / 1000)  # sleep 50 ms to 150 ms
                else:  # don't try again
                    return False
            else:
                self.disconnect()
                return not self.is_login_error(response.code)

    def disconnect(self):
        """Close the connection."""
        try:
            self.client.send(commands.Logout())
            self.client.close()
        except Exception:
            logger.warning("Connection to registry was not cleanly closed.")

    def send(self, command):
        response = self.client.send(command)
        if response.code >= 2000:
            self.client.close()
            raise LoginError(response.msg)

        return response
