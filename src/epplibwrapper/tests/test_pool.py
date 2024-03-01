import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from dateutil.tz import tzlocal  # type: ignore
from django.test import TestCase
from epplibwrapper.client import EPPLibWrapper
from epplibwrapper.errors import RegistryError
from registrar.models.domain import registry
from contextlib import ExitStack
from .common import less_console_noise
import logging

try:
    from epplib import commands
    from epplib.client import Client
    from epplib.exceptions import TransportError
    from epplib.transport import SocketTransport
    from epplib.models import common, info
except ImportError:
    pass

logger = logging.getLogger(__name__)


class TestConnectionPool(TestCase):
    """Tests for our connection pooling behaviour"""

    # def setUp(self):
    #     # Mimic the settings added to settings.py
    #     self.pool_options = {
    #         # Current pool size
    #         "size": 1,
    #         # Which errors the pool should look out for
    #         "exc_classes": (TransportError,),
    #         # Occasionally pings the registry to keep the connection alive.
    #         # Value in seconds => (keepalive / size)
    #         "keepalive": 60,
    #     }

    # def fake_socket(self, login, client):
    #     # Linter reasons
    #     pw = "none"
    #     # Create a fake client object
    #     fake_client = Client(
    #         SocketTransport(
    #             "none",
    #             cert_file="path/to/cert_file",
    #             key_file="path/to/key_file",
    #             password=pw,
    #         )
    #     )

    #     return Socket(fake_client, MagicMock())

    # def patch_success(self):
    #     return True

    # def fake_send(self, command, cleaned=None):
    #     mock = MagicMock(
    #         code=1000,
    #         msg="Command completed successfully",
    #         res_data=None,
    #         cl_tr_id="xkw1uo#2023-10-17T15:29:09.559376",
    #         sv_tr_id="5CcH4gxISuGkq8eqvr1UyQ==-35a",
    #         extensions=[],
    #         msg_q=None,
    #     )
    #     return mock

    # def fake_client(mock_client):
    #     pw = "none"
    #     client = Client(
    #         SocketTransport(
    #             "none",
    #             cert_file="path/to/cert_file",
    #             key_file="path/to/key_file",
    #             password=pw,
    #         )
    #     )
    #     return client

    # @patch.object(EPPLibWrapper, "_test_registry_connection_success", patch_success)
    # def test_pool_sends_data(self):
    #     """A .send is invoked on the pool successfully"""
    #     expected_result = {
    #         "cl_tr_id": None,
    #         "code": 1000,
    #         "extensions": [],
    #         "msg": "Command completed successfully",
    #         "msg_q": None,
    #         "res_data": [
    #             info.InfoDomainResultData(
    #                 roid="DF1340360-GOV",
    #                 statuses=[
    #                     common.Status(
    #                         state="serverTransferProhibited",
    #                         description=None,
    #                         lang="en",
    #                     ),
    #                     common.Status(state="inactive", description=None, lang="en"),
    #                 ],
    #                 cl_id="gov2023-ote",
    #                 cr_id="gov2023-ote",
    #                 cr_date=datetime.datetime(2023, 8, 15, 23, 56, 36, tzinfo=tzlocal()),
    #                 up_id="gov2023-ote",
    #                 up_date=datetime.datetime(2023, 8, 17, 2, 3, 19, tzinfo=tzlocal()),
    #                 tr_date=None,
    #                 name="test3.gov",
    #                 registrant="TuaWnx9hnm84GCSU",
    #                 admins=[],
    #                 nsset=None,
    #                 keyset=None,
    #                 ex_date=datetime.date(2024, 8, 15),
    #                 auth_info=info.DomainAuthInfo(pw="2fooBAR123fooBaz"),
    #             )
    #         ],
    #         "sv_tr_id": "wRRNVhKhQW2m6wsUHbo/lA==-29a",
    #     }

    #     # Mock a response from EPP
    #     def fake_receive(command, cleaned=None):
    #         location = Path(__file__).parent / "utility" / "infoDomain.xml"
    #         xml = (location).read_bytes()
    #         return xml

    #     def do_nothing(command):
    #         pass

    #     # Mock what happens inside the "with"
    #     with ExitStack() as stack:
    #         stack.enter_context(patch.object(EPPConnectionPool, "_create_socket", self.fake_socket))
    #         stack.enter_context(patch.object(Socket, "connect", self.fake_client))
    #         stack.enter_context(patch.object(EPPConnectionPool, "kill_all_connections", do_nothing))
    #         stack.enter_context(patch.object(SocketTransport, "send", self.fake_send))
    #         stack.enter_context(patch.object(SocketTransport, "receive", fake_receive))
    #         with less_console_noise():
    #             # Restart the connection pool
    #             registry.start_connection_pool()
    #             # Pool should be running, and be the right size
    #             self.assertEqual(registry.pool_status.connection_success, True)
    #             self.assertEqual(registry.pool_status.pool_running, True)

    #             # Send a command
    #             result = registry.send(commands.InfoDomain(name="test.gov"), cleaned=True)

    #             # Should this ever fail, it either means that the schema has changed,
    #             # or the pool is broken.
    #             # If the schema has changed: Update the associated infoDomain.xml file
    #             self.assertEqual(result.__dict__, expected_result)

    #             # The number of open pools should match the number of requested ones.
    #             # If it is 0, then they failed to open
    #             self.assertEqual(len(registry._pool.conn), self.pool_options["size"])
    #             # Kill the connection pool
    #             registry.kill_pool()

    # @patch.object(EPPLibWrapper, "_test_registry_connection_success", patch_success)
    # def test_pool_restarts_on_send(self):
    #     """A .send is invoked, but the pool isn't running.
    #     The pool should restart."""
    #     expected_result = {
    #         "cl_tr_id": None,
    #         "code": 1000,
    #         "extensions": [],
    #         "msg": "Command completed successfully",
    #         "msg_q": None,
    #         "res_data": [
    #             info.InfoDomainResultData(
    #                 roid="DF1340360-GOV",
    #                 statuses=[
    #                     common.Status(
    #                         state="serverTransferProhibited",
    #                         description=None,
    #                         lang="en",
    #                     ),
    #                     common.Status(state="inactive", description=None, lang="en"),
    #                 ],
    #                 cl_id="gov2023-ote",
    #                 cr_id="gov2023-ote",
    #                 cr_date=datetime.datetime(2023, 8, 15, 23, 56, 36, tzinfo=tzlocal()),
    #                 up_id="gov2023-ote",
    #                 up_date=datetime.datetime(2023, 8, 17, 2, 3, 19, tzinfo=tzlocal()),
    #                 tr_date=None,
    #                 name="test3.gov",
    #                 registrant="TuaWnx9hnm84GCSU",
    #                 admins=[],
    #                 nsset=None,
    #                 keyset=None,
    #                 ex_date=datetime.date(2024, 8, 15),
    #                 auth_info=info.DomainAuthInfo(pw="2fooBAR123fooBaz"),
    #             )
    #         ],
    #         "sv_tr_id": "wRRNVhKhQW2m6wsUHbo/lA==-29a",
    #     }

    #     # Mock a response from EPP
    #     def fake_receive(command, cleaned=None):
    #         location = Path(__file__).parent / "utility" / "infoDomain.xml"
    #         xml = (location).read_bytes()
    #         return xml

    #     def do_nothing(command):
    #         pass

    #     # Mock what happens inside the "with"
    #     with ExitStack() as stack:
    #         stack.enter_context(patch.object(EPPConnectionPool, "_create_socket", self.fake_socket))
    #         stack.enter_context(patch.object(Socket, "connect", self.fake_client))
    #         stack.enter_context(patch.object(EPPConnectionPool, "kill_all_connections", do_nothing))
    #         stack.enter_context(patch.object(SocketTransport, "send", self.fake_send))
    #         stack.enter_context(patch.object(SocketTransport, "receive", fake_receive))
    #         with less_console_noise():
    #             # Start the connection pool
    #             registry.start_connection_pool()
    #             # Kill the connection pool
    #             registry.kill_pool()

    #             self.assertEqual(registry.pool_status.pool_running, False)

    #             # An exception should be raised as end user will be informed
    #             # that they cannot connect to EPP
    #             with self.assertRaises(RegistryError):
    #                 expected = "InfoDomain failed to execute due to a connection error."
    #                 result = registry.send(commands.InfoDomain(name="test.gov"), cleaned=True)
    #                 self.assertEqual(result, expected)

    #             # A subsequent command should be successful, as the pool restarts
    #             result = registry.send(commands.InfoDomain(name="test.gov"), cleaned=True)
    #             # Should this ever fail, it either means that the schema has changed,
    #             # or the pool is broken.
    #             # If the schema has changed: Update the associated infoDomain.xml file
    #             self.assertEqual(result.__dict__, expected_result)

    #             # The number of open pools should match the number of requested ones.
    #             # If it is 0, then they failed to open
    #             self.assertEqual(len(registry._pool.conn), self.pool_options["size"])
    #             # Kill the connection pool
    #             registry.kill_pool()

    # @patch.object(EPPLibWrapper, "_test_registry_connection_success", patch_success)
    # def test_raises_connection_error(self):
    #     """A .send is invoked on the pool, but registry connection is lost
    #     right as we send a command."""

    #     with ExitStack() as stack:
    #         stack.enter_context(patch.object(EPPConnectionPool, "_create_socket", self.fake_socket))
    #         stack.enter_context(patch.object(Socket, "connect", self.fake_client))
    #         with less_console_noise():
    #             # Start the connection pool
    #             registry.start_connection_pool()

    #             # Pool should be running
    #             self.assertEqual(registry.pool_status.connection_success, True)
    #             self.assertEqual(registry.pool_status.pool_running, True)

    #             # Try to send a command out - should fail
    #             with self.assertRaises(RegistryError):
    #                 expected = "InfoDomain failed to execute due to a connection error."
    #                 result = registry.send(commands.InfoDomain(name="test.gov"), cleaned=True)
    #                 self.assertEqual(result, expected)
