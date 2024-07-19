import datetime
from dateutil.tz import tzlocal  # type: ignore
from unittest.mock import MagicMock, patch
from pathlib import Path
from django.test import TestCase
from api.tests.common import less_console_noise_decorator
from gevent.exceptions import ConcurrentObjectUseError
from epplibwrapper.client import EPPLibWrapper
from epplibwrapper.errors import RegistryError, LoginError
import logging

try:
    from epplib.exceptions import TransportError
    from epplib.responses import Result
    from epplib.transport import SocketTransport
    from epplib import commands
    from epplib.models import common, info
except ImportError:
    pass

logger = logging.getLogger(__name__)


class TestClient(TestCase):
    """Test the EPPlibwrapper client"""

    @less_console_noise_decorator
    def fake_result(self, code, msg):
        """Helper function to create a fake Result object"""
        return Result(code=code, msg=msg, res_data=[], cl_tr_id="cl_tr_id", sv_tr_id="sv_tr_id")

    @less_console_noise_decorator
    @patch("epplibwrapper.client.Client")
    def test_initialize_client_success(self, mock_client):
        """Test when the initialize_client is successful"""
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

    @less_console_noise_decorator
    @patch("epplibwrapper.client.Client")
    def test_initialize_client_transport_error(self, mock_client):
        """Test when the send(login) step of initialize_client raises a TransportError."""
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

    @less_console_noise_decorator
    @patch("epplibwrapper.client.Client")
    def test_initialize_client_login_error(self, mock_client):
        """Test when the send(login) step of initialize_client returns (2400) comamnd failed code."""
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

    @less_console_noise_decorator
    @patch("epplibwrapper.client.Client")
    def test_initialize_client_unknown_exception(self, mock_client):
        """Test when the send(login) step of initialize_client raises an unexpected Exception."""
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

    @less_console_noise_decorator
    @patch("epplibwrapper.client.Client")
    def test_initialize_client_fails_recovers_with_send_command(self, mock_client):
        """Test when the initialize_client fails on the connect() step. And then a subsequent
        call to send() should recover and re-initialize the client and properly return
        the successful send command.
        Flow:
        Initialization step fails at app init
        Send command fails (with 2400 code) prompting retry
        Client closes and re-initializes, and command is sent successfully"""
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

    @less_console_noise_decorator
    @patch("epplibwrapper.client.Client")
    def test_send_command_failed_retries_and_fails_again(self, mock_client):
        """Test when the send("InfoDomainCommand) call fails with a 2400, prompting a retry
        and the subsequent send("InfoDomainCommand) call also fails with a 2400, raise
        a RegistryError
        Flow:
        Initialization succeeds
        Send command fails (with 2400 code) prompting retry
        Client closes and re-initializes, and command fails again with 2400"""
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
        # connect() should be called twice, once during initialization, second time
        # during retry
        self.assertEquals(mock_connect.call_count, 2)
        # close() is called once during retry
        mock_close.assert_called_once()
        # send() is called 5 times: send(login), send(command) fails, send(logout)
        # send(login), send(command)
        self.assertEquals(mock_send.call_count, 5)

    @less_console_noise_decorator
    @patch("epplibwrapper.client.Client")
    def test_send_command_failure_prompts_successful_retry(self, mock_client):
        """Test when the send("InfoDomainCommand) call fails with a 2400, prompting a retry
        and the subsequent send("InfoDomainCommand) call succeeds
        Flow:
        Initialization succeeds
        Send command fails (with 2400 code) prompting retry
        Client closes and re-initializes, and command succeeds"""
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
        # connect() is called twice, once during initialization of app, once during retry
        self.assertEquals(mock_connect.call_count, 2)
        # close() is called once, during retry
        mock_close.assert_called_once()
        # send() is called 5 times: send(login), send(command) fail, send(logout), send(login), send(command)
        self.assertEquals(mock_send.call_count, 5)

    @less_console_noise_decorator
    def fake_failure_send_concurrent_threads(self, command=None, cleaned=None):
        """
        Raises a ConcurrentObjectUseError, which gevent throws when accessing
        the same thread from two different locations.
        """
        # This error is thrown when two threads are being used concurrently
        raise ConcurrentObjectUseError("This socket is already used by another greenlet")

    def do_nothing(self, command=None):
        """
        A placeholder method that performs no action.
        """
        pass  # noqa

    @less_console_noise_decorator
    def fake_success_send(self, command=None, cleaned=None):
        """
        Simulates receiving a success response from EPP.
        """
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

    @less_console_noise_decorator
    def fake_info_domain_received(self, command=None, cleaned=None):
        """
        Simulates receiving a response by reading from a predefined XML file.
        """
        location = Path(__file__).parent / "utility" / "infoDomain.xml"
        xml = (location).read_bytes()
        return xml

    @less_console_noise_decorator
    def get_fake_epp_result(self):
        """Mimics a return from EPP by returning a dictionary in the same format"""
        result = {
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
        return result

    @less_console_noise_decorator
    def test_send_command_close_failure_recovers(self):
        """
        Validates the resilience of the connection handling mechanism
        during command execution on retry.

        Scenario:
        - Initialization of the connection is successful.
        - An attempt to send a command fails with a specific error code (ConcurrentObjectUseError)
        - The client attempts to retry.
        - Subsequently, the client re-initializes the connection.
        - A retry of the command execution post-reinitialization succeeds.
        """
        expected_result = self.get_fake_epp_result()
        wrapper = None
        # Trigger a retry
        # Do nothing on connect, as we aren't testing it and want to connect while
        # mimicking the rest of the client as closely as possible (which is not entirely possible with MagicMock)
        with patch.object(EPPLibWrapper, "_connect", self.do_nothing):
            with patch.object(SocketTransport, "send", self.fake_failure_send_concurrent_threads):
                wrapper = EPPLibWrapper()
                tested_command = commands.InfoDomain(name="test.gov")
                try:
                    wrapper.send(tested_command, cleaned=True)
                except RegistryError as err:
                    expected_error = "InfoDomain failed to execute due to an unknown error."
                    self.assertEqual(err.args[0], expected_error)
                else:
                    self.fail("Registry error was not thrown")

        # After a retry, try sending again to see if the connection recovers
        with patch.object(EPPLibWrapper, "_connect", self.do_nothing):
            with patch.object(SocketTransport, "send", self.fake_success_send), patch.object(
                SocketTransport, "receive", self.fake_info_domain_received
            ):
                result = wrapper.send(tested_command, cleaned=True)
                self.assertEqual(expected_result, result.__dict__)
