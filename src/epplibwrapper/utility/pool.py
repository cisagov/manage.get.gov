import logging
import queue
import threading
import time
from contextlib import contextmanager

try:
    from epplib.commands import Hello, Logout
    from epplib.exceptions import TransportError
except ImportError:
    pass

logger = logging.getLogger(__name__)

class PoolExhausted(Exception):
    """No connection became available within the checkout timeout.
    Raised only when the pool is at max size AND every connection stayed
    checked out for the entire wait. 
    
    Translates into a RegistryError. Investigate this one when seen.
    """
##TODO- remove retire!

class PooledConnection:
    """One logged-in epplib client plus the bookkeeping the pool needs.

    last_ping  is a timestamp (monotonic--> immune to wall-clock changes).
    It is refreshed on checkin, AND on every successful heartbeat ping
    so now- last_ping represents how long it's been since the connection
    proved it was alive.
    """

    def __init__(self, client):
        self.client = client
        self.last_ping= time.monotonic()

class EPPConnectionPool:
    def __init__(
        self,
        connection_factory,
        size,
        borrow_timeout,
        idle_ping_seconds,
        heartbeat_interval,
    ):
        self._connection_factory = connection_factory
        self.size = size
        self.borrow_timeout = borrow_timeout
        self.idle_ping_seconds = idle_ping_seconds
        self.heartbeat_interval = heartbeat_interval

        # LIFO stack of idle connections: the most recently returned
        # connection is handed out first. The oldest connections
        # settle at the bottom and eventually age past idle_ping_seconds,
        # where the heartbeat pings them.
        self._idle: queue.LifoQueue = queue.LifoQueue(maxsize=size)

        #counts connections that exist, including ones in use (checked out) 
        # and ones in the idle stack. This is used to enforce the pool size limit.
        # _connections_created can never be > size
        self._connections_created = 0

        # as long as the architecture uses Gevent, this will not create a true python thread
        # Gunicorn will spawn a greenlet instead. If we ever switch to gthread this code 
        # will still work but will create a true thread. (aka this is also thread-safe)
        self._creation_lock  = threading.Lock()

        # Fill the Queue of connections to begin with
        self._replenish()

        # Background maintenance thread. daemon=True means it never blocks process shutdown. 
        # Under gevent it runs as a greenlet, under gthread it is a real OS thread. 
        # No changes needed. Set to None if you don't want a heartbeat thread.
        
        if heartbeat_interval:
            # While load testing, having a heartbeat thread proved to reduce EPP connection errors
            # However, the pool can function without it. 
            self._maintenance_thread = threading.Thread(
                target=self._maintenance_loop, daemon=True, name="epp-pool-maintenance"
            )
            self._maintenance_thread.start()

    @contextmanager
    def connection(self):
        """Borrow a healthy connection, return it once the epp call is finished.
        
        Usage:
            with pool.connection() as conn:
                response = conn.send(command)

        You must follow the above usage pattern. Do not call the epplib function Client.send() 
        or Epplibwrapper.send() directly outside of the with block. 
        
        Exception handling: 
        - TransportError: socket connection is likely bad -> discard it! The next borrow 
        call will create a new connection to replace it.
        - Any other exception (command rejected, parsing problem, LoginError, etc): 
        the transport is presumed fine -> connection will be returned to the pool for reuse.
        In these cases, look for credential or command logic errors.
        """
        conn = self._borrow()
        try:
            yield conn.client
        except TransportError:
            # the socket is likely dead. Discard it and let the pool create a new one.
            self._discard(conn)

            # Raise error to enforce a retry
            raise 

        except Exception:
            # the transport is presumed fine. Return it to the pool for reuse.
            self._return_connection(conn)
            raise
        else:
            # no exception, return it to the pool for reuse.
            self._return_connection(conn)
    
    def close_all(self):
        """Close all idle connections cleanly
        logout from registry + close the socket. 
        Called at worker shut down
        Note: threads still using a connection will not be interrupted."""
        while True:
            try:
                conn = self._idle.get_nowait()
                self._retire(conn)
            except queue.Empty:
                break

    def stats(self):
        """Pool snapshot, embedded in log messages.

        connections created = connections in existence (checked out + idle)
        idle    = connections currently waiting in the queue
        
        """
        return {"size": self.size, "connections created": self._connections_created, "idle": self._idle.qsize(), "in use": self._connections_created - self._idle.qsize()}
    
    def _borrow(self) -> PooledConnection:
        """
        Borrow a connection from the pool, replace stale ones if needed.

        Loop until a healthy connection is found or the borrow timeout expires.

        Raises:
            PoolExhausted: if no connection becomes available within the borrow timeout.
        """
        # Deadline is time when borrow expires, if can't borrow within this time, 
        # raise PoolExhausted.
        deadline = time.monotonic() + self.borrow_timeout
        while True:
            conn = self._get_or_create(deadline)
            if self._is_healthy(conn):
                return conn
            
            # Health check failed. Discard it + try again. 
            # This is expected every once in a while,
            # however, if is happening continuously back to back investigate
            # Network issues, registry issues, or a bug in the health check logic.
            logger.info("Discarding stale pooled EPP connection; will replace. %s",self.stats())
            self._discard(conn)

    
    def _get_or_create(self, deadline) -> PooledConnection:
        """
        Fetch a connection

        Args:
            deadline: float, monotonic time when the borrow timeout expires

        Raises:
            PoolExhausted: if no connection becomes available within the borrow timeout.
        
        Returns:
            PooledConnection: a connection from the pool
        """
        logger.debug("Getting a connection from the pool. Pool stats: %s", self.stats())
        
        # Step 1: Try to get an idle connection from the pool without waiting.
        try:
            conn = self._idle.get_nowait()
            return conn
        except queue.Empty:
            # Don't error on an empty queue, just move to creating a connection
            pass
        
        # Step 2: Couldn't get an idle connection, create a new one if possible
        if self._can_create():
            try:
                return PooledConnection(self._connection_factory())
            except Exception:
                logger.debug("Failed to create a new connection. Pool stats: %s", self.stats())
                self._release_slot()
                raise
        
        # Step 3: Pool is at max size, wait for a connection to be returned to the pool
        # only wait for the remaining time until the deadline.
        remaining = deadline - time.monotonic()
        try:
            return self._idle.get(timeout=max(remaining, 0))
        except queue.Empty:
            logger.debug("No EPP connection available after %s. %s", self.borrow_timeout, self.stats())
            raise PoolExhausted(f"No EPP connection available after {self.borrow_timeout}s. {self.stats()}")
    
    def _is_healthy(self, conn: PooledConnection) -> bool:
        """Decide whether a connection can be handed to a caller.
        
        - Recently-used connections are trusted as-is.
        - A connection idle past the idle max seconds must answer an
        EPP `Hello` first-> idle sockets can be silently dropped, hello checks for this.
        """
        if time.monotonic() - conn.last_ping < self.idle_ping_seconds:
            return True
        try:
            # we just want to check once if the connection is alive, and if not, chuck it.
            # _borrow() handles the actual discard/replacement logic.
            conn.client.send(Hello())
            conn.last_ping = time.monotonic()
            return True
        except Exception:
            return False
    
    def _maintenance_loop(self):
        """
        Forever: sleep, then run one maintenance pass over idle connections.
        Any unexpected error is logged and the loop continues.
        """
        while self.heartbeat_interval > 0:
            time.sleep(self.heartbeat_interval)
            try:
                self._maintain_idle_connections()
            except Exception:
                logger.warning("EPP pool heartbeat pass failed. Once is fine, but investigate if you see multiple back to back. Stats: %s", self.stats(),exc_info=True)

    def _maintain_idle_connections(self):
        """
        Ping each idle connection that hasn't proven itself alive recently.
        Return the healthy ones to the pool, discard the dead ones.
        """

        # snapshot holds the idle queue at this point in time
        # fill snapshot with all IDLE connections.
        snapshot = []
        while True:
            try:
                # Pop items from Q into snapshot
                conn = self._idle.get_nowait()
                snapshot.append(conn)
            except queue.Empty:
                break

        # for each conn. 1.) return it to the Q if it recently proved it was alive
        # 2.) if it's been unpinged too long ping it & return it to Q if it's healthy,
        # 3.) if the ping fails, discard it.

        now = time.monotonic()

        for conn in snapshot:
            last_ping_idle_time = now - conn.last_ping

            # if the time since the last ping is greater than the ping threshold,
            # ping to see if it's still alive
            if last_ping_idle_time > self.idle_ping_seconds:
                is_healthy = self._is_healthy(conn)
                if is_healthy:
                    self._return_connection(conn)
                else:
                    logger.info("Heartbeat replaced a dead idle EPP connection. %s", self.stats())
                    self._discard(conn)
            else:
                # recently proved alive, no need to ping it
                self._put_back(conn)

        self._replenish()

    def _replenish(self):
        """ Refills queue if 1 or more connections were discarded/retired
        otherwise does nothing
        """
        while self._connections_created <self.size and self._can_create():
            try:
                self._put_back(PooledConnection(self._connection_factory()))
            except Exception:
                self._release_slot()
                logger.info("Replenish hit an error & failed to build a connection. Stats: %s", self.stats())
                break
    def _can_create(self) -> bool:
        """True if able to create one more connection. False if at capacity.
        updates the _connections_created counter"""
        with self._creation_lock :
            if self._connections_created < self.size:
                self._connections_created += 1
                return True
            else:
                return False
    def _return_connection(self, conn: PooledConnection):
        """Return after the connection proved itself alive (real command or ping)."""
        conn.last_ping = time.monotonic()
        self._put_back(conn)

    def _put_back(self, conn: PooledConnection):
        self._idle.put(conn)

    def _release_slot(self):
        """Give back a slot after its connection is closed (discard/retire)."""
        with self._creation_lock:
            self._connections_created -= 1

    def _discard(self, conn: PooledConnection):
        """Dispose of a connection presumed DEAD.
        """
        try:
            conn.client.close()
        except Exception:
            logger.debug("Error occurred while closing connection. Pool stats: %s", self.stats(), exc_info=True)
            # ignore any errors during close, we are discarding the connection anyway
            pass
        self._release_slot()

    def _retire(self, conn: PooledConnection):
        """"Dispose of a HEALTHY connection we simply no longer need.
        used by close_all at worker shutdown
        """
        try:
            conn.client.send(Logout())
        except Exception:
            logger.info("Error occurred while retiring connection. Pool stats: %s", self.stats(), exc_info=True)
            # ignore any errors during logout, we are discarding the connection anyway
            pass
        try:
            conn.client.close()
        except Exception:
            logger.info("Error occurred while closing connection. Pool stats: %s", self.stats(), exc_info=True)
            pass
        self._release_slot()

