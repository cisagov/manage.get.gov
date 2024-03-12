import datetime
import logging
from unittest.mock import MagicMock, patch
from django.test import TestCase
from epplibwrapper.client import EPPLibWrapper
from epplibwrapper.errors import RegistryError, LoginError
from .common import less_console_noise
from pathlib import Path
from dateutil.tz import tzlocal  # type: ignore
from registrar.models.domain import registry
from contextlib import ExitStack

try:
    from epplib.exceptions import TransportError
    from epplib.responses import Result
    from epplib import commands
    from epplib.client import Client
    from epplib.transport import SocketTransport
    from epplib.models import common, info
except ImportError:
    pass


logger = logging.getLogger(__name__)


class TestClient(TestCase):
    """Test the EPPlibwrapper client"""

    def fake_result(self, code, msg):
        """Helper function to create a fake Result object"""
        return Result(code=code, msg=msg, res_data=[], cl_tr_id="cl_tr_id", sv_tr_id="sv_tr_id")

    def fake_client(self):
        # Create a fake client object
        pw="none"
        fake_client = Client(
            SocketTransport(
                "none",
                cert_file="path/to/cert_file",
                key_file="path/to/key_file",
                password=pw,
            )
        )

        return fake_client

    @patch("epplibwrapper.client.Client")
    def test_initialize_client_success(self, mock_client):
        """Test when the initialize_client is successful"""
        with less_console_noise():
            # Mock the Client instance and its methods
            mock_connect = MagicMock()
            # Create a mock Result instance
            mock_result = MagicMock(spec=Result)
            mock_result.code = 200
            mock_result.msg = "Success"
            mock_result.res_data = ["data1", "data2"]
            mock_result.cl_tr_id = "client_id"
            mock_result.sv_tr_id = "server_id"
            mock_send = MagicMock(return_value=mock_result)
            mock_client.return_value.connect = mock_connect
            mock_client.return_value.send = mock_send

            # Create EPPLibWrapper instance and initialize client
            wrapper = EPPLibWrapper()

            # Assert that connect method is called once
            mock_connect.assert_called_once()
            # Assert that _client is not None after initialization
            self.assertIsNotNone(wrapper._client)

    @patch("epplibwrapper.client.Client")
    def test_initialize_client_transport_error(self, mock_client):
        """Test when the send(login) step of initialize_client raises a TransportError."""
        with less_console_noise():
            # Mock the Client instance and its methods
            mock_connect = MagicMock()
            mock_send = MagicMock(side_effect=TransportError("Transport error"))
            mock_client.return_value.connect = mock_connect
            mock_client.return_value.send = mock_send

            with self.assertRaises(RegistryError):
                # Create EPPLibWrapper instance and initialize client
                # if functioning as expected, initial __init__ should except
                # and log any Exception raised
                wrapper = EPPLibWrapper()
                # so call _initialize_client a second time directly to test
                # the raised exception
                wrapper._initialize_client()

    @patch("epplibwrapper.client.Client")
    def test_initialize_client_login_error(self, mock_client):
        """Test when the send(login) step of initialize_client returns (2400) comamnd failed code."""
        with less_console_noise():
            # Mock the Client instance and its methods
            mock_connect = MagicMock()
            # Create a mock Result instance
            mock_result = MagicMock(spec=Result)
            mock_result.code = 2400
            mock_result.msg = "Login failed"
            mock_result.res_data = ["data1", "data2"]
            mock_result.cl_tr_id = "client_id"
            mock_result.sv_tr_id = "server_id"
            mock_send = MagicMock(return_value=mock_result)
            mock_client.return_value.connect = mock_connect
            mock_client.return_value.send = mock_send

            with self.assertRaises(LoginError):
                # Create EPPLibWrapper instance and initialize client
                # if functioning as expected, initial __init__ should except
                # and log any Exception raised
                wrapper = EPPLibWrapper()
                # so call _initialize_client a second time directly to test
                # the raised exception
                wrapper._initialize_client()

    @patch("epplibwrapper.client.Client")
    def test_initialize_client_unknown_exception(self, mock_client):
        """Test when the send(login) step of initialize_client raises an unexpected Exception."""
        with less_console_noise():
            # Mock the Client instance and its methods
            mock_connect = MagicMock()
            mock_send = MagicMock(side_effect=Exception("Unknown exception"))
            mock_client.return_value.connect = mock_connect
            mock_client.return_value.send = mock_send

            with self.assertRaises(RegistryError):
                # Create EPPLibWrapper instance and initialize client
                # if functioning as expected, initial __init__ should except
                # and log any Exception raised
                wrapper = EPPLibWrapper()
                # so call _initialize_client a second time directly to test
                # the raised exception
                wrapper._initialize_client()

    @patch("epplibwrapper.client.Client")
    def test_initialize_client_fails_recovers_with_send_command(self, mock_client):
        """Test when the initialize_client fails on the connect() step. And then a subsequent
        call to send() should recover and re-initialize the client and properly return
        the successful send command.
        Flow:
        Initialization step fails at app init
        Send command fails (with 2400 code) prompting retry
        Client closes and re-initializes, and command is sent successfully"""
        with less_console_noise(), patch(Client, 'send', return_value=mock_send_response) as mock_send:
            # Mock the Client instance and its methods
            # close() should return successfully
            mock_close = MagicMock()
            mock_client.return_value.close = mock_close
            # Create success and failure results
            command_success_result = self.fake_result(1000, "Command completed successfully")
            command_failure_result = self.fake_result(2400, "Command failed")
            # side_effect for the connect() calls
            # first connect() should raise an Exception
            # subsequent connect() calls should return success
            connect_call_count = 0

            def connect_side_effect(*args, **kwargs):
                nonlocal connect_call_count
                connect_call_count += 1
                if connect_call_count == 1:
                    raise Exception("Connection failed")
                else:
                    return command_success_result

            mock_connect = MagicMock(side_effect=connect_side_effect)
            mock_client.return_value.connect = mock_connect
            # side_effect for the send() calls
            # first send will be the send("InfoDomainCommand") and should fail
            # subsequend send() calls should return success
            send_call_count = 0

            def send_side_effect(*args, **kwargs):
                nonlocal send_call_count
                send_call_count += 1
                if send_call_count == 1:
                    return command_failure_result
                else:
                    return command_success_result

            mock_send = MagicMock(side_effect=send_side_effect)
            print(f"what is mock client? {mock_client}")
            mock_client.return_value.send = mock_send
            # Create EPPLibWrapper instance and call send command
            wrapper = EPPLibWrapper()
            wrapper.send("InfoDomainCommand", cleaned=True)
            # two connect() calls should be made, the initial failed connect()
            # and the successful connect() during retry()
            self.assertEquals(mock_connect.call_count, 2)
            # close() should only be called once, during retry()
            mock_close.assert_called_once()
            # send called 4 times: failed send("InfoDomainCommand"), passed send(logout),
            # passed send(login), passed send("InfoDomainCommand")
            self.assertEquals(mock_send.call_count, 4)

    @patch("epplibwrapper.client.Client")
    def test_send_command_failed_retries_and_fails_again(self, mock_client):
        """Test when the send("InfoDomainCommand) call fails with a 2400, prompting a retry
        and the subsequent send("InfoDomainCommand) call also fails with a 2400, raise
        a RegistryError
        Flow:
        Initialization succeeds
        Send command fails (with 2400 code) prompting retry
        Client closes and re-initializes, and command fails again with 2400"""
        with less_console_noise():
            # Mock the Client instance and its methods
            # connect() and close() should succeed throughout
            mock_connect = MagicMock()
            mock_close = MagicMock()
            # Create a mock Result instance
            send_command_success_result = self.fake_result(1000, "Command completed successfully")
            send_command_failure_result = self.fake_result(2400, "Command failed")

            # side_effect for send command, passes for all other sends (login, logout), but
            # fails for send("InfoDomainCommand")
            def side_effect(*args, **kwargs):
                if args[0] == "InfoDomainCommand":
                    return send_command_failure_result
                else:
                    return send_command_success_result

            mock_send = MagicMock(side_effect=side_effect)
            mock_client.return_value.connect = mock_connect
            mock_client.return_value.close = mock_close
            mock_client.return_value.send = mock_send

            with self.assertRaises(RegistryError):
                # Create EPPLibWrapper instance and initialize client
                wrapper = EPPLibWrapper()
                # call send, which should throw a RegistryError (after retry)
                wrapper.send("InfoDomainCommand", cleaned=True)
            # connect() should be called thrice, for each thread
            self.assertEquals(mock_connect.call_count, 3)
            # close() is called once during retry
            mock_close.assert_called_once()
            # send() is called 4 times: send(login), send(command) fails, send(logout)
            # send(login)
            self.assertEquals(mock_send.call_count, 4)

    @patch("epplibwrapper.client.Client")
    def test_send_command_failure_prompts_successful_retry(self, mock_client):
        """Test when the send("InfoDomainCommand) call fails with a 2400, prompting a retry
        and the subsequent send("InfoDomainCommand) call succeeds
        Flow:
        Initialization succeeds
        Send command fails (with 2400 code) prompting retry
        Client closes and re-initializes, and command succeeds"""
        with less_console_noise():
            # Mock the Client instance and its methods
            # connect() and close() should succeed throughout
            mock_connect = MagicMock()
            mock_close = MagicMock()
            # create success and failure result messages
            send_command_success_result = self.fake_result(1000, "Command completed successfully")
            send_command_failure_result = self.fake_result(2400, "Command failed")
            # side_effect for send call, initial send(login) succeeds during initialization, next send(command)
            # fails, subsequent sends (logout, login, command) all succeed
            send_call_count = 0

            def side_effect(*args, **kwargs):
                nonlocal send_call_count
                send_call_count += 1
                if send_call_count == 2:
                    return send_command_failure_result
                else:
                    return send_command_success_result

            mock_send = MagicMock(side_effect=side_effect)
            mock_client.return_value.connect = mock_connect
            mock_client.return_value.close = mock_close
            mock_client.return_value.send = mock_send
            # Create EPPLibWrapper instance and initialize client
            wrapper = EPPLibWrapper()
            wrapper.send("InfoDomainCommand", cleaned=True)
            # connect() is called thrice, for each thread
            self.assertEquals(mock_connect.call_count, 3)
            # close() is called once on this thread, during retry
            mock_close.assert_called_once()
            # send() is called 4 times: send(login), send(command) fail, send(logout), send(command)
            self.assertEquals(mock_send.call_count, 4)


class TestConnectionPool(TestCase):
    """Tests for our connection pooling behaviour"""

    def fake_client(self):
        # Create a fake client object
        pw="none"
        fake_client = Client(
            SocketTransport(
                "none",
                cert_file="path/to/cert_file",
                key_file="path/to/key_file",
                password=pw,
            )
        )

        return fake_client

    def patch_success(self):
        return True

    def fake_send(self, command, cleaned=None):
        mock = MagicMock(
            code=1000,
            msg="Command completed successfully",
            res_data=None,
            cl_tr_id="xkw1uo#2023-10-17T15:29:09.559376",
            sv_tr_id="5CcH4gxISuGkq8eqvr1UyQ==-35a",
            extensions=[],
            msg_q=None,
        )
        return mock

    def fake_client(mock_client):
        pw = "none"
        client = Client(
            SocketTransport(
                "none",
                cert_file="path/to/cert_file",
                key_file="path/to/key_file",
                password=pw,
            )
        )
        return client

    @patch("epplibwrapper.client.Client")
    def test_pool_sends_data(self, mock_client):
        """A .send is invoked on the pool successfully"""
        expected_result = {
            "cl_tr_id": None,
            "code": 1000,
            "extensions": [],
            "msg": "Command completed successfully",
            "msg_q": None,
            "res_data": [
                info.InfoDomainResultData(
                    roid="DF1340360-GOV",
                    statuses=[
                        common.Status(
                            state="serverTransferProhibited",
                            description=None,
                            lang="en",
                        ),
                        common.Status(state="inactive", description=None, lang="en"),
                    ],
                    cl_id="gov2023-ote",
                    cr_id="gov2023-ote",
                    cr_date=datetime.datetime(2023, 8, 15, 23, 56, 36, tzinfo=tzlocal()),
                    up_id="gov2023-ote",
                    up_date=datetime.datetime(2023, 8, 17, 2, 3, 19, tzinfo=tzlocal()),
                    tr_date=None,
                    name="test3.gov",
                    registrant="TuaWnx9hnm84GCSU",
                    admins=[],
                    nsset=None,
                    keyset=None,
                    ex_date=datetime.date(2024, 8, 15),
                    auth_info=info.DomainAuthInfo(pw="2fooBAR123fooBaz"),
                )
            ],
            "sv_tr_id": "wRRNVhKhQW2m6wsUHbo/lA==-29a",
        }

        # Mock a response from EPP
        def fake_receive(command, cleaned=None):
            location = Path(__file__).parent / "utility" / "infoDomain.xml"
            xml = (location).read_bytes()
            return xml

        mock_connect = MagicMock()
        mock_close = MagicMock()
        self.maxDiff = None
        # Mock what happens inside the "with"
        with ExitStack() as stack:
            stack.enter_context(patch.object(EPPLibWrapper, "_send_to_epp", self.fake_send))
            stack.enter_context(patch.object(SocketTransport, "receive", fake_receive))
            mock_client.return_value.connect = mock_connect
            mock_client.return_value.close = mock_close
            with less_console_noise():

                # Send a command
                result = registry.send(commands.InfoDomain(name="test.gov"), cleaned=True)

                # Should this ever fail, it either means that the schema has changed,
                # or the pool is broken.
                # If the schema has changed: Update the associated infoDomain.xml file
                self.assertEqual(result.__dict__, expected_result)


    @patch.object(EPPLibWrapper, "_test_registry_connection_success", patch_success)
    def test_pool_restarts_on_send(self):
        """A .send is invoked, but the pool isn't running.
        The pool should restart."""
        expected_result = {
            "cl_tr_id": None,
            "code": 1000,
            "extensions": [],
            "msg": "Command completed successfully",
            "msg_q": None,
            "res_data": [
                info.InfoDomainResultData(
                    roid="DF1340360-GOV",
                    statuses=[
                        common.Status(
                            state="serverTransferProhibited",
                            description=None,
                            lang="en",
                        ),
                        common.Status(state="inactive", description=None, lang="en"),
                    ],
                    cl_id="gov2023-ote",
                    cr_id="gov2023-ote",
                    cr_date=datetime.datetime(2023, 8, 15, 23, 56, 36, tzinfo=tzlocal()),
                    up_id="gov2023-ote",
                    up_date=datetime.datetime(2023, 8, 17, 2, 3, 19, tzinfo=tzlocal()),
                    tr_date=None,
                    name="test3.gov",
                    registrant="TuaWnx9hnm84GCSU",
                    admins=[],
                    nsset=None,
                    keyset=None,
                    ex_date=datetime.date(2024, 8, 15),
                    auth_info=info.DomainAuthInfo(pw="2fooBAR123fooBaz"),
                )
            ],
            "sv_tr_id": "wRRNVhKhQW2m6wsUHbo/lA==-29a",
        }

        # Mock a response from EPP
        def fake_receive(command, cleaned=None):
            location = Path(__file__).parent / "utility" / "infoDomain.xml"
            xml = (location).read_bytes()
            return xml

        def do_nothing(command):
            pass

        # Mock what happens inside the "with"
        with ExitStack() as stack:
            stack.enter_context(patch.object(Client, "connect", self.fake_client))
            stack.enter_context(patch.object(SocketTransport, "send", self.fake_send))
            stack.enter_context(patch.object(SocketTransport, "receive", fake_receive))
            with less_console_noise():
                # Start the connection pool
                registry.start_connection_pool()
                # Kill the connection pool
                registry.kill_pool()

                self.assertEqual(registry.pool_status.pool_running, False)

                # An exception should be raised as end user will be informed
                # that they cannot connect to EPP
                with self.assertRaises(RegistryError):
                    expected = "InfoDomain failed to execute due to a connection error."
                    result = registry.send(commands.InfoDomain(name="test.gov"), cleaned=True)
                    self.assertEqual(result, expected)

                # A subsequent command should be successful, as the pool restarts
                result = registry.send(commands.InfoDomain(name="test.gov"), cleaned=True)
                # Should this ever fail, it either means that the schema has changed,
                # or the pool is broken.
                # If the schema has changed: Update the associated infoDomain.xml file
                self.assertEqual(result.__dict__, expected_result)

                # The number of open pools should match the number of requested ones.
                # If it is 0, then they failed to open
                self.assertEqual(len(registry._pool.conn), self.pool_options["size"])
                # Kill the connection pool
                registry.kill_pool()

    @patch.object(EPPLibWrapper, "_test_registry_connection_success", patch_success)
    def test_raises_connection_error(self):
        """A .send is invoked on the pool, but registry connection is lost
        right as we send a command."""

        with ExitStack() as stack:
            stack.enter_context(patch.object(EPPConnectionPool, "_create_socket", self.fake_socket))
            stack.enter_context(patch.object(Socket, "connect", self.fake_client))
            with less_console_noise():
                # Start the connection pool
                registry.start_connection_pool()

                # Pool should be running
                self.assertEqual(registry.pool_status.connection_success, True)
                self.assertEqual(registry.pool_status.pool_running, True)

                # Try to send a command out - should fail
                with self.assertRaises(RegistryError):
                    expected = "InfoDomain failed to execute due to a connection error."
                    result = registry.send(commands.InfoDomain(name="test.gov"), cleaned=True)
                    self.assertEqual(result, expected)