from unittest import skip
from unittest.mock import patch
from django.conf import settings

from django.test import Client
from epplibwrapper.client import EPPLibWrapper
from registrar.tests.common import MockEppLib

import logging

try:
    from epplib.client import Client
    from epplib import commands
    from epplib.exceptions import TransportError
    from epplib.transport import SocketTransport
except ImportError:
    pass

logger = logging.getLogger(__name__)


@patch("djangooidc.views.CLIENT", autospec=True)
class TestConnectionPool(MockEppLib):
    """Tests for our connection pooling behaviour"""

    def setUp(self):
        """
        Background:
            Given the registrant is logged in
            And the registrant is the admin on a domain
        """
        super().setUp()
        self.pool_options = {
            # Current pool size
            "size": 1,
            # Which errors the pool should look out for
            "exc_classes": (TransportError,),
            # Occasionally pings the registry to keep the connection alive.
            # Value in seconds => (keepalive / size)
            "keepalive": 60,
        }

    def tearDown(self):
        super().tearDown()

    def user_info(*args):
        return {
            "sub": "TEST",
            "email": "test@example.com",
            "first_name": "Testy",
            "last_name": "Tester",
            "phone": "814564000",
        }

    def test_pool_created_successfully(self, mock_client):
        # setup
        session = self.client.session
        session["state"] = "TEST"  # nosec B105
        session.save()
        # mock
        mock_client.callback.side_effect = self.user_info

        client = EPPLibWrapper()
        pool = client._pool

        # These are defined outside of the pool,
        # so we can reimplement how this is being done
        # in client.py. They should remain unchanged,
        # and if they aren't, something went wrong.
        expected_login = commands.Login(
            cl_id="nothing",
            password="nothing",
            obj_uris=[
                "urn:ietf:params:xml:ns:domain-1.0",
                "urn:ietf:params:xml:ns:contact-1.0",
            ],
            new_pw=None,
            version="1.0",
            lang="en",
            ext_uris=[],
        )

        # Key/cert will generate a new file everytime.
        # This should never be null, so we can check for that.
        try:
            expected_client = Client(
                SocketTransport(
                    settings.SECRET_REGISTRY_HOSTNAME,
                    cert_file=pool._client.transport.cert_file,
                    key_file=pool._client.transport.key_file,
                    password=settings.SECRET_REGISTRY_KEY_PASSPHRASE,
                )
            ).__dict__
        except Exception as err:
            self.fail(err)

        # We don't care about checking if the objects are both of
        # the same reference, we only care about data parity, so
        # we do a dict conversion.
        actual_client = pool._client.__dict__
        actual_client["transport"] = actual_client["transport"].__dict__
        expected_client["transport"] = expected_client["transport"].__dict__

        # Ensure that we're getting the credentials we expect
        self.assertEqual(pool._login, expected_login)
        self.assertEqual(actual_client, expected_client)

        # Check that options are set correctly
        self.assertEqual(pool.size, self.pool_options["size"])
        self.assertEqual(pool.keepalive, self.pool_options["keepalive"])
        self.assertEqual(pool.exc_classes, self.pool_options["exc_classes"])

        # Check that it is running
        self.assertEqual(client.pool_status.connection_success, True)
        self.assertEqual(client.pool_status.pool_running, True)

    @skip("not implemented yet")
    def test_pool_timesout(self):
        """The pool timesout and restarts"""
        raise

    @skip("not implemented yet")
    def test_multiple_users_send_data(self):
        """Multiple users send data concurrently"""
        raise

    @skip("not implemented yet")
    def test_pool_sends_data(self):
        """A .send is invoked on the pool"""
        raise
