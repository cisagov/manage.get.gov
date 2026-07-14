"""Tests for the EPP connection pool: borrow/return, health checks on checkout,
discard/replace, replenish, and shutdown.

Every pool here is built with heartbeat_interval=0 so no maintenance thread
starts — the heartbeat/maintenance loop is not covered yet.
"""

import time
from unittest.mock import MagicMock

from django.test import TestCase
from api.tests.common import less_console_noise_decorator

from epplibwrapper.utility.pool import EPPConnectionPool, PoolExhausted

try:
    from epplib.commands import Hello, Logout
    from epplib.exceptions import TransportError
except ImportError:
    pass


class TestEPPConnectionPool(TestCase):
    """Test EPPConnectionPool checkout/checkin lifecycle logic."""

    def setUp(self):
        super().setUp()
        # every client the factory handed out, in creation order
        self.created_clients = []

    def factory(self):
        """Stand-in for EPPLibWrapper._create_connection - returns a mock client."""
        client = MagicMock()
        self.created_clients.append(client)
        return client

    def make_pool(self, size=1, borrow_timeout=0.05, idle_ping_seconds=60, factory=None):
        """Build a pool with the maintenance thread disabled."""
        return EPPConnectionPool(
            connection_factory=factory if factory is not None else self.factory,
            size=size,
            borrow_timeout=borrow_timeout,
            idle_ping_seconds=idle_ping_seconds,
            heartbeat_interval=0,
        )

    @less_console_noise_decorator
    def test_init_fills_pool_to_size(self):
        """On creation the pool immediately builds `size` connections, all idle."""
        pool = self.make_pool(size=3)
        self.assertEqual(len(self.created_clients), 3)
        self.assertEqual(pool.stats(), {"size": 3, "connections created": 3, "idle": 3, "in use": 0})

    @less_console_noise_decorator
    def test_init_survives_factory_failure(self):
        """If the registry is down at startup, the pool constructs empty instead of raising."""

        def bad_factory():
            raise TransportError("registry unreachable")

        pool = self.make_pool(size=2, factory=bad_factory)
        self.assertEqual(pool.stats(), {"size": 2, "connections created": 0, "idle": 0, "in use": 0})

    @less_console_noise_decorator
    def test_connection_yields_client_and_returns_it_to_pool(self):
        """connection() hands out the raw client and checks it back in afterwards."""
        pool = self.make_pool(size=1)
        with pool.connection() as client:
            self.assertIs(client, self.created_clients[0])
            self.assertEqual(pool.stats(), {"size": 1, "connections created": 1, "idle": 0, "in use": 1})
        self.assertEqual(pool.stats(), {"size": 1, "connections created": 1, "idle": 1, "in use": 0})

    @less_console_noise_decorator
    def test_connection_reuses_the_same_connection(self):
        """Back-to-back checkouts reuse one connection rather than creating more."""
        pool = self.make_pool(size=1)
        with pool.connection() as first:
            pass
        with pool.connection() as second:
            pass
        self.assertIs(first, second)
        self.assertEqual(len(self.created_clients), 1)

    @less_console_noise_decorator
    def test_most_recently_returned_connection_is_handed_out_first(self):
        """The idle queue is LIFO: the last connection returned is the next one borrowed."""
        pool = self.make_pool(size=2)
        conn_a = pool._borrow()
        conn_b = pool._borrow()
        pool._return_connection(conn_a)
        pool._return_connection(conn_b)
        self.assertIs(pool._borrow(), conn_b)

    @less_console_noise_decorator
    def test_transport_error_discards_connection(self):
        """A TransportError inside the with block closes the connection and frees its slot."""
        pool = self.make_pool(size=1)
        with self.assertRaises(TransportError):
            with pool.connection():
                raise TransportError("socket died")
        self.created_clients[0].close.assert_called_once()
        self.assertEqual(pool.stats(), {"size": 1, "connections created": 0, "idle": 0, "in use": 0})

    @less_console_noise_decorator
    def test_non_transport_error_returns_connection_to_pool(self):
        """Any non-transport error presumes the socket is fine and checks the connection back in."""
        pool = self.make_pool(size=1)
        with self.assertRaises(ValueError):
            with pool.connection():
                raise ValueError("command rejected")
        self.created_clients[0].close.assert_not_called()
        self.assertEqual(pool.stats(), {"size": 1, "connections created": 1, "idle": 1, "in use": 0})

    @less_console_noise_decorator
    def test_borrow_replaces_discarded_connection(self):
        """After a discard, the next checkout builds a fresh connection to fill the slot."""
        pool = self.make_pool(size=1)
        with self.assertRaises(TransportError):
            with pool.connection():
                raise TransportError("socket died")
        with pool.connection() as client:
            self.assertIs(client, self.created_clients[1])
        self.assertEqual(len(self.created_clients), 2)
        self.assertEqual(pool.stats(), {"size": 1, "connections created": 1, "idle": 1, "in use": 0})

    @less_console_noise_decorator
    def test_fresh_connection_is_not_pinged_on_borrow(self):
        """A recently-active connection is trusted as-is - no Hello before handing it out."""
        pool = self.make_pool(size=1)
        with pool.connection():
            pass
        self.created_clients[0].send.assert_not_called()

    @less_console_noise_decorator
    def test_stale_connection_is_pinged_before_reuse(self):
        """A connection idle past idle_ping_seconds must answer a Hello before being handed out."""
        pool = self.make_pool(size=1, idle_ping_seconds=60)
        conn = pool._borrow()
        conn.last_ping = time.monotonic() - 120
        pool._put_back(conn)  # bypass the checkin stamps so the connection stays stale

        with pool.connection() as client:
            self.assertIs(client, self.created_clients[0])

        # exactly one Hello was sent during checkout, and the checkout still reused the connection
        hello_calls = [c for c in self.created_clients[0].send.call_args_list if isinstance(c.args[0], Hello)]
        self.assertEqual(len(hello_calls), 1)
        self.assertEqual(len(self.created_clients), 1)

    @less_console_noise_decorator
    def test_stale_connection_failing_ping_is_replaced(self):
        """If the Hello fails, the stale connection is discarded and a new one is created."""
        pool = self.make_pool(size=1, idle_ping_seconds=60)
        conn = pool._borrow()
        conn.last_ping = time.monotonic() - 120
        conn.client.send.side_effect = TransportError("connection silently dropped")
        pool._put_back(conn)  # bypass the checkin stamps so the connection stays stale

        with pool.connection() as client:
            self.assertIs(client, self.created_clients[1])
        self.created_clients[0].close.assert_called_once()
        self.assertEqual(pool.stats(), {"size": 1, "connections created": 1, "idle": 1, "in use": 0})

    @less_console_noise_decorator
    def test_pool_exhausted_when_all_connections_checked_out(self):
        """When every connection stays checked out past the borrow timeout, raise PoolExhausted."""
        pool = self.make_pool(size=1, borrow_timeout=0.05)
        held = pool._borrow()
        with self.assertRaises(PoolExhausted):
            pool._borrow()
        # once a connection is returned, borrowing works again
        pool._return_connection(held)
        self.assertIs(pool._borrow(), held)

    @less_console_noise_decorator
    def test_factory_failure_during_borrow_releases_the_slot(self):
        """A failed creation gives its slot back so a later attempt can retry."""
        attempts = {"count": 0}

        def flaky_factory():
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise TransportError("registry unreachable")
            return self.factory()

        # the initial replenish fails, leaving an empty pool with the slot released
        pool = self.make_pool(size=1, factory=flaky_factory)
        self.assertEqual(pool.stats()["connections created"], 0)

        # the next checkout uses the freed slot to build a working connection
        with pool.connection() as client:
            self.assertIs(client, self.created_clients[0])
        self.assertEqual(pool.stats(), {"size": 1, "connections created": 1, "idle": 1, "in use": 0})

    @less_console_noise_decorator
    def test_borrow_raises_factory_error(self):
        """If creating a replacement connection fails, the caller sees the factory's error."""

        def bad_factory():
            raise TransportError("registry unreachable")

        pool = self.make_pool(size=1, factory=bad_factory)
        with self.assertRaises(TransportError):
            with pool.connection():
                pass
        self.assertEqual(pool.stats()["connections created"], 0)

    @less_console_noise_decorator
    def test_can_create_stops_at_size(self):
        """_can_create enforces the pool size cap and only increments when a slot is free."""
        pool = self.make_pool(size=2)
        self.assertFalse(pool._can_create())
        self.assertEqual(pool._connections_created, 2)
        pool._release_slot()
        self.assertTrue(pool._can_create())
        self.assertEqual(pool._connections_created, 2)

    @less_console_noise_decorator
    def test_return_connection_refreshes_ping_clock(self):
        """Checking in stamps last_ping, so the connection is trusted as fresh."""
        pool = self.make_pool(size=1)
        conn = pool._borrow()
        conn.last_ping = 0.0
        before = time.monotonic()
        pool._return_connection(conn)
        self.assertGreaterEqual(conn.last_ping, before)

    @less_console_noise_decorator
    def test_replenish_refills_after_discard(self):
        """_replenish rebuilds connections up to size after one was discarded."""
        pool = self.make_pool(size=2)
        conn = pool._borrow()
        pool._discard(conn)
        self.assertEqual(pool.stats()["connections created"], 1)
        pool._replenish()
        self.assertEqual(pool.stats(), {"size": 2, "connections created": 2, "idle": 2, "in use": 0})

    @less_console_noise_decorator
    def test_close_all_retires_idle_connections(self):
        """close_all logs out and closes every idle connection."""
        pool = self.make_pool(size=2)
        pool.close_all()
        for client in self.created_clients:
            self.assertIsInstance(client.send.call_args.args[0], Logout)
            client.close.assert_called_once()
        self.assertEqual(pool.stats(), {"size": 2, "connections created": 0, "idle": 0, "in use": 0})

    @less_console_noise_decorator
    def test_close_all_leaves_checked_out_connections_alone(self):
        """close_all only drains the idle queue - in-flight connections are not interrupted."""
        pool = self.make_pool(size=2)
        held = pool._borrow()
        pool.close_all()
        held.client.close.assert_not_called()
        self.assertEqual(pool.stats(), {"size": 2, "connections created": 1, "idle": 0, "in use": 1})

    @less_console_noise_decorator
    def test_retire_closes_socket_even_if_logout_fails(self):
        """A failed Logout during retirement still closes the socket and frees the slot."""
        pool = self.make_pool(size=1)
        self.created_clients[0].send.side_effect = Exception("logout failed")
        pool.close_all()
        self.created_clients[0].close.assert_called_once()
        self.assertEqual(pool.stats()["connections created"], 0)
