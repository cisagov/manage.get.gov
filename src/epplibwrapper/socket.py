from django.conf import settings

try:
    from epplib.transport import SocketTransport

    class TimeoutSocketTransport(SocketTransport):
        """SocketTransport that applies a socket timeout after connecting.

        The stock SocketTransport sets no socket timeout, so a slow or dead
        registry makes recv() block indefinitely while holding the connection
        lock. Instead of relying on SocketTransport alone, this code uses
        settings.EPP_CONNECTION_TIMEOUT to timeout the connection with a 
        socket.timeout error which epplib surfaces as a TransportError that 
        our send()/retry path already handles.

        This needs to be in a try/except block because epplib is not installed in local dev.
        """

        def connect(self) -> None:
            super().connect()
            self.socket.settimeout(settings.EPP_CONNECTION_TIMEOUT)  # type: ignore

except ImportError:
    pass
