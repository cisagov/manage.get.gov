from django.conf import settings

try:
    from epplib.transport import SocketTransport

    class TimeoutSocketTransport(SocketTransport):
        """SocketTransport that applies a socket timeout after connecting.

        The stock SocketTransport sets no socket timeout, so a slow or dead
        registry makes a subsequent recv()/send() block indefinitely while
        holding the connection lock. This applies settings.EPP_CONNECTION_TIMEOUT
        once connect() has returned, so reads and sends raise a socket.timeout
        (which epplib surfaces as a TransportError that our send()/retry path
        already handles) instead of hanging.

        Note: this only bounds reads/sends after the connection is established;
        the initial TCP connect() in the parent class is not bounded here.

        This needs to be in a try/except block because epplib is not installed in local dev.
        """

        def connect(self) -> None:
            super().connect()
            self.socket.settimeout(settings.EPP_CONNECTION_TIMEOUT)  # type: ignore

except ImportError:
    pass
