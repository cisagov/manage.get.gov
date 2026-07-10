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
# https://medium.com/@artemkhrenov/connection-pooling-patterns-optimizing-database-connections-for-scalable-applications-159e78281389
logger = logging.getLogger(__name__)

class PoolExhausted(Exception):
    """No connection became available within the checkout timeout.
    Raised only when the pool is at max size AND every connection stayed
    checked out for the entire wait. 
    
    Translates into a RegistryError. Investigate this one when seen.
    """
   # TODO add error mesage

class PooledConnection:
    """One logged-in epplib client plus the bookkeeping the pool needs.

    last_used is a timestamp (monotonic--> immune to wall-clock changes).
    It is refreshed on checkin and on every successful heartbeat ping, so
    "idle time" always means time since the connection last did real work
    or proved itself alive.
    """

    def __init__(self, client):
        self.client = client
        self.last_used = time.monotonic()
        self.last_ping= time.monotonic()
    
    def send(self, command):
        response =super.send()
        if command != Hello ():
            self.last_used = time.monotonic()
            self.last_ping= time.monotonic()
        return response

class EPPConnectionPool:
    def __init__(
        self,
        connection_factory,
        size,
        borrow_timeout,
        idle_ping_seconds,
        heartbeat_interval,
        idle_recycle_seconds,
    ):
        self._connection_factory = connection_factory
        self.size = size
        self.borrow_timeout = borrow_timeout
        self.idle_ping_seconds = idle_ping_seconds
        self.heartbeat_interval = heartbeat_interval
        self.idle_recycle_seconds = idle_recycle_seconds
        
        # LIFO stack of idle connections: the most recently returned
        # connection is handed out first. The oldest connections
        # settle at the bottom and eventually age past idle_recycle_seconds,
        # where the heartbeat retires them - that's how the pool shrinks.
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
        
        if heartbeat_interval or idle_max_seconds:
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
                response = client.send(command)

        You must follow the above usage pattern. Do not call conn.client.send() 
        
        Exception handling: 
        - TransportError: socket connection is likely bad -> discard it! The next borrow 
        call will create a new connection to replace it.
        - Any other exception (command rejected, parsing problem, LoginError, etc): 
        the transport is presumed fine -> connection will be returned to the pool for reuse.
        In these cases, look for creditional or command logic errors.
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
        
        # Step 1: Try to get an idle connection from the pool, waiting up to the borrow timeout.
        try:
            conn = self._idle.get(timeout=max(0, deadline - time.monotonic()))
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
            logger.debug("No EPP connection available after %s. %s", self.checkout_timeout, self.stats())
            raise PoolExhausted(f"No EPP connection available after {self.checkout_timeout}s. {self.stats()}")
    
    def _is_healthy(self, conn: PooledConnection) -> bool:
        """Decide whether a connection can be handed to a caller.
        
        - Recently-used connections are trusted as-is.
        - A connection idle past the idle max seconds must answer an
        EPP `Hello` first-> idle sockets can be silently dropped, hello checks for this.
        """
        if time.monotonic() - conn.last_ping < self.idle_ping_seconds:
            return True
        try:
            # note: this is NOT using conn.client.send() because send()
            # recursively calls itself if the hello fails. 
            # we just want to check once if the connection is alive, and if not, chuck it.
            # _borrow() handles the actual discard/replacement logic.
            conn.client._send(Hello())
            conn.last_ping = time.monotonic()
            return True
        except Exception:
            return False
    
    def _maintenance_loop(self):
        """
        Forever: sleep, then run one maintenance pass over idle connections.
        Any unexpected error is logged and the loop continues.
        """
        use_heartbeat = False
        loop_interval= self.idle_max_seconds
        
        if self.heartbeat_interval is not None and self.heartbeat_interval > 0:
            use_heartbeat = True
            loop_interval = self.heartbeat_interval

        while loop_interval>0:
            time.sleep(loop_interval)
            try:
                self._maintain_idle_connections(use_heartbeat=use_heartbeat, retire_old_connections=self.idle_max_seconds>0)
            except Exception:
                logger.warning("EPP pool heartbeat pass failed. Once is fine, but investigate if you see multiple back to back. Stats: %s", self.stats(),exc_info=True)
    
    def _maintain_idle_connections(self, use_heartbeat: bool, retire_old_connections:bool):
        """
        Ping each idle connection to see if it is still alive.
        If a connection has been idle for more than idle_max_seconds, retire it.
        """

        # snapshot holds the idle queue at this point in time
        snapshot = []
        if retire_old_connections or use_heartbeat:
            # fill snapshot with all IDLE connections.
            while True:
                try:
                    # Pop items from Q into snapshot
                    conn = self._idle.get_nowait()
                    snapshot.append(conn)
                except queue.Empty:
                    break
            
            #for each conn. 1.) return it to the Q if recently used
            # 2.) if it's been idle too long ping it & return it to Q if it's healthy,
            # 3.) If it's been idle too long the ping fails, discard it.
            # 3.) if it's dead just toss (retire) the connection.
            
            now = time.monotonic()
            
            for conn in snapshot:
                idle_time = now - conn.last_used
                last_ping_idle_time = now - conn.last_ping

                # if the conn. has been idle too long
                if retire_old_connections and idle_time > self.idle_max_seconds :
                    
                        logger.info("Retiring long-idle EPP connection (pool shrinks). %s", self.stats())
                        self._retire(conn=conn)
                        logger.debug("After retire. Pool stats: %s", self.stats())
                            
                # if the idle time is greater than the ping threshold, 
                # ping to see if it's still alive
                elif use_heartbeat and last_ping_idle_time > self.idle_ping_seconds :
                    logger.debug("Discarding stale connection during heartbeat. %s", self.stats())
                    is_healthy = self._is_healthy(conn)
                    if is_healthy:
                        self._return_connection(conn)   
                    else:
                        logger.info("Heartbeat replaced a dead idle EPP connection. %s", self.stats())
                        self._discard(conn)
                else:
                    # recently used, no need to ping it
                    self._idle.put(conn)
                
        self._replenish()

    def _replenish(self):
        """ Refills queue if 1 or more connections were discarded/retired
        otherwise does nothing
        """
        while self._connections_created <self.size and self._reserve_slot():
            try:
                self._idle.put(PooledConnection(self._connection_factory()))
            except Exception:
                self._release_slot()
                logger.info("Replenish hit and error & failed to build a connection. Stats: %s", self.stats()) 
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
    def _reserve_slot(self)-> bool:
        """Wait on lock to be able to create one connection if not at size yet"""
        with self._created_lock:
            if self._created <self.size:
                self._created+=1
                return True
            return False
        
    def _return_connection(self, conn: PooledConnection):
        """Return a connection to the idle queue after successful use."""
        now = time.monotonic()
        conn.last_used = now
        conn.last_ping = now
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
        used by the idle connection heartbeat to shrink the pool & close_all
        """
        try:
            conn.client.send(Logout())
            conn.client.close()
        except Exception:
            logger.debug("Error occurred while retiring connection. Pool stats: %s", self.stats(), exc_info=True)
            # ignore any errors during logout, we are discarding the connection anyway
            pass
        self._release_slot()