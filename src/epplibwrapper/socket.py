import logging

try:
    from epplib import commands
except ImportError:
    pass

from .errors import LoginError


logger = logging.getLogger(__name__)


class Socket:
    """Context manager which establishes a TCP connection with registry."""

    def __init__(self, client, login) -> None:
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
        if response.code >= 2000:
            self.client.close()
            raise LoginError(response.msg)
        return self.client

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
