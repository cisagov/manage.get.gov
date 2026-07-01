import socket
from typing import cast

from django.conf import settings

try:
    from epplib.transport import SocketTransport

    class TimeoutSocketTransport(SocketTransport):
        """SocketTransport that applies a socket timeout and enables TCP keepalive
        after connecting.

        The stock SocketTransport sets no socket timeout, so a slow or dead
        registry makes a subsequent recv()/send() block indefinitely while
        holding the connection lock. This applies settings.EPP_CONNECTION_TIMEOUT
        once connect() has returned, so reads and sends raise a socket.timeout
        (which epplib surfaces as a TransportError that our send()/retry path
        already handles) instead of hanging.

        It also enables OS-level TCP keepalive so the kernel keeps an otherwise
        idle connection warm and detects a dropped peer. This keeps the long-lived
        EPP socket from being silently reaped by the network path during idle
        periods.

        Note: this only bounds reads/sends after the connection is established;
        the initial TCP connect() in the parent class is not bounded here. The
        TCP_KEEP* tuning options are Linux-only, so each is applied only if the
        platform exposes it (prod runs Linux; local dev skips epplib entirely).

        This needs to be in a try/except block because epplib is not installed in local dev.
        """

        def connect(self) -> None:
            super().connect()
            sock = cast(socket.socket, self.socket)
            sock.settimeout(settings.EPP_CONNECTION_TIMEOUT)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if hasattr(socket, "TCP_KEEPIDLE"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, settings.EPP_KEEPALIVE_IDLE)
            if hasattr(socket, "TCP_KEEPINTVL"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, settings.EPP_KEEPALIVE_INTERVAL)
            if hasattr(socket, "TCP_KEEPCNT"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, settings.EPP_KEEPALIVE_COUNT)

except ImportError:
    pass
