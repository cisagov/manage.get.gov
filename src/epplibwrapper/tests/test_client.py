from unittest.mock import MagicMock, patch
from django.test import TestCase
from epplibwrapper.client import EPPLibWrapper
from epplibwrapper.errors import RegistryError, LoginError
from .common import less_console_noise
import logging

try:
    from epplib.exceptions import TransportError
    from epplib.responses import Result
except ImportError:
    pass

logger = logging.getLogger(__name__)


class TestClient(TestCase):
    """Test the EPPlibwrapper client"""

    def fake_result(self, code, msg):
        """Helper function to create a fake Result object"""
        return Result(code=code, msg=msg, res_data=[], cl_tr_id="cl_tr_id", sv_tr_id="sv_tr_id")

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
        with less_console_noise():
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
            # connect() should be called twice, once during initialization, second time
            # during retry
            self.assertEquals(mock_connect.call_count, 2)
            # close() is called once during retry
            mock_close.assert_called_once()
            # send() is called 5 times: send(login), send(command) fails, send(logout)
            # send(login), send(command)
            self.assertEquals(mock_send.call_count, 5)

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
            # connect() is called twice, once during initialization of app, once during retry
            self.assertEquals(mock_connect.call_count, 2)
            # close() is called once, during retry
            mock_close.assert_called_once()
            # send() is called 5 times: send(login), send(command) fail, send(logout), send(login), send(command)
            self.assertEquals(mock_send.call_count, 5)
