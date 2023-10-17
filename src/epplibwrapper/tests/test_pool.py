from unittest import skip
from unittest.mock import MagicMock, patch
from django.conf import settings

from django.test import TestCase
from epplibwrapper.client import EPPLibWrapper
from epplibwrapper.socket import Socket
from epplibwrapper.utility.pool import EPPConnectionPool
from registrar.models.domain import Domain
from registrar.models.domain import registry
from contextlib import ExitStack

import logging

try:
    from epplib import commands
    from epplib.exceptions import TransportError
except ImportError:
    pass

logger = logging.getLogger(__name__)


class TestConnectionPool(TestCase):
    """Tests for our connection pooling behaviour"""

    def setUp(self):
        self.pool_options = {
            # Current pool size
            "size": 1,
            # Which errors the pool should look out for
            "exc_classes": (TransportError,),
            # Occasionally pings the registry to keep the connection alive.
            # Value in seconds => (keepalive / size)
            "keepalive": 60,
        }

        # Mock a successful connection
        self.mock_connect_patch = patch("epplib.client.Client.connect")
        self.mocked_connect_function = self.mock_connect_patch.start()
        self.mocked_connect_function.side_effect = self.mock_connect

        # Mock the send behaviour
        self.mock_send_patch = patch("epplib.client.Client.send")
        self.mocked_send_function = self.mock_send_patch.start()
        self.mocked_send_function.side_effect = self.mock_send

        # Mock the pool object
        self.mockSendPatch = patch("registrar.models.domain.registry._pool")
        self.mockedSendFunction = self.mockSendPatch.start()
        self.mockedSendFunction.side_effect = self.fake_pool

    def tearDown(self):
        self.mock_send_patch.stop()
        self.mock_connect_patch.stop()
        self.mockSendPatch.stop()

    def mock_connect(self, _request):
        return None

    def mock_send(self, _request):
        if isinstance(_request, commands.Login):
            response = MagicMock(
                code=1000,
                msg="Command completed successfully",
                res_data=None,
                cl_tr_id="xkw1uo#2023-10-17T15:29:09.559376",
                sv_tr_id="5CcH4gxISuGkq8eqvr1UyQ==-35a",
                extensions=[],
                msg_q=None,
            )

            return response
        return None

    def user_info(self, *args):
        return {
            "sub": "TEST",
            "email": "test@example.com",
            "first_name": "Testy",
            "last_name": "Tester",
            "phone": "814564000",
        }

    @patch("djangooidc.views.CLIENT", autospec=True)
    def fake_pool(self, mock_client):
        # mock client
        mock_client.callback.side_effect = self.user_info
        # Create a mock transport object
        mock_login = MagicMock()
        mock_login.cert_file = "path/to/cert_file"
        mock_login.key_file = "path/to/key_file"

        pool = EPPConnectionPool(
            client=mock_client, login=mock_login, options=self.pool_options
        )
        return pool

    @skip("not implemented yet")
    def test_pool_timesout(self):
        """The pool timesout and restarts"""
        raise

    @skip("not implemented yet")
    def test_multiple_users_send_data(self):
        """Multiple users send data concurrently"""
        raise

    def test_pool_tries_create_invalid(self):
        """A .send is invoked on the pool, but the pool
        shouldn't be running."""
        # Fake data for the _pool object
        domain, _ = Domain.objects.get_or_create(name="freeman.gov")

        # Trigger the getter - should fail
        expected_contact = domain.security_contact
        self.assertEqual(registry.pool_status.pool_running, False)
        self.assertEqual(registry.pool_status.connection_success, False)
        self.assertEqual(len(registry._pool.conn), 0)

    def test_pool_sends_data(self):
        """A .send is invoked on the pool successfully"""
        # Fake data for the _pool object
        domain, _ = Domain.objects.get_or_create(name="freeman.gov")
        
        def fake_send(self):
            return MagicMock(
                code=1000,
                msg="Command completed successfully",
                res_data=None,
                cl_tr_id="xkw1uo#2023-10-17T15:29:09.559376",
                sv_tr_id="5CcH4gxISuGkq8eqvr1UyQ==-35a",
                extensions=[],
                msg_q=None,
            )

        with ExitStack() as stack:
            stack.enter_context(patch.object(Socket, "connect", None))
            stack.enter_context(patch.object(Socket, "send", fake_send))
            stack.enter_context(patch.object(Socket, "_create_socket", Socket()))
            #stack.enter_context(patch.object(EPPLibWrapper, "get_pool", self.fake_pool))
            pool = EPPLibWrapper(False)
            # The connection pool will fail to start, start it manually
            # so that our mocks can take over
            pool.start_connection_pool(try_start_if_invalid=True)
            print(f"this is pool {pool._pool.__dict__}")
            # Pool should be running, and be the right size
            self.assertEqual(pool.pool_status.pool_running, True)
            self.assertEqual(pool.pool_status.connection_success, True)
            pool.send(commands.InfoDomain(name="test.gov"), cleaned=True)
            self.assertEqual(len(pool._pool.conn), self.pool_options["size"])

            #pool.send()
            
            # Trigger the getter - should succeed
            #expected_contact = domain.security_contact


