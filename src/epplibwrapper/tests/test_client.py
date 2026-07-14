"""Tests for the EPPLibWrapper client: connection creation/login and the
send/retry logic layered on top of the connection pool.

The pool's own borrow/return/discard mechanics are covered in test_pool.py.
The pool maintenance heartbeat is intentionally not tested yet.
"""

import datetime
from dateutil.tz import tzlocal  # type: ignore
from unittest.mock import MagicMock, patch
from pathlib import Path
from django.test import TestCase, override_settings
from api.tests.common import less_console_noise_decorator
from gevent.exceptions import ConcurrentObjectUseError
from epplibwrapper.client import EPPLibWrapper
from epplibwrapper.errors import ErrorCode, RegistryError, LoginError
import logging

try:
    from epplib.exceptions import TransportError, ParsingError
    from epplib.responses import Result
    from epplib.transport import SocketTransport
    from epplib import commands
    from epplib.models import common, info
except ImportError:
    pass

logger = logging.getLogger(__name__)


@override_settings(
    EPP_CONNECTION_POOL_SIZE=1,
    EPP_POOL_BORROW_TIMEOUT=1,
    EPP_POOL_IDLE_PING_SECONDS=60,
    # TODO - COME Back here when heartbeat code is merged in!
    EPP_POOL_HEARTBEAT_INTERVAL=0,
)
class TestClient(TestCase):
    """Test the EPPlibwrapper client"""

    def fake_result(self, code, msg):
        """Helper function to create a fake Result object"""
        return Result(code=code, msg=msg, res_data=[], cl_tr_id="cl_tr_id", sv_tr_id="sv_tr_id")

    def fake_success_result(self):
        return self.fake_result(1000, "Command completed successfully")

    def fake_command(self):
        """A real epplib command to send through the wrapper."""
        return commands.InfoDomain(name="test.gov")

    @less_console_noise_decorator
    @patch("epplibwrapper.client.Client")
    def test_pool_created_with_successful_connection(self, mock_client):
        """On init the wrapper builds the pool, which connects and logs in one client."""
        mock_client.return_value.send = MagicMock(return_value=self.fake_success_result())

        wrapper = EPPLibWrapper()

        mock_client.return_value.connect.assert_called_once()
        # the one send was the login command prepared in __init__
        mock_client.return_value.send.assert_called_once_with(wrapper._login)
        self.assertEqual(wrapper._pool.stats(), {"size": 1, "connections created": 1, "idle": 1, "in use": 0})

    @less_console_noise_decorator
    @patch("epplibwrapper.client.Client")
    def test_wrapper_initializes_even_when_registry_is_down(self, mock_client):
        """A connection failure at startup leaves the pool empty but does not raise."""
        mock_client.return_value.connect = MagicMock(side_effect=TransportError("registry unreachable"))

        wrapper = EPPLibWrapper()

        self.assertEqual(wrapper._pool.stats(), {"size": 1, "connections created": 0, "idle": 0, "in use": 0})

    @less_console_noise_decorator
    @patch("epplibwrapper.client.Client")
    def test_create_connection_transport_error(self, mock_client):
        """A TransportError while connecting becomes a RegistryError with the transport code."""
        mock_client.return_value.connect = MagicMock(side_effect=TransportError("registry unreachable"))
        wrapper = EPPLibWrapper()

        with self.assertRaises(RegistryError)as command_response:
            wrapper._create_connection()
        self.assertEqual(command_response.exception.code, ErrorCode.TRANSPORT_ERROR)
        self.assertTrue(command_response.exception.is_transport_error())

    @less_console_noise_decorator
    @patch("epplibwrapper.client.Client")
    def test_create_connection_login_error(self, mock_client):
        """A failure code (2400) in the login response raises LoginError and closes the client."""
        mock_client.return_value.send = MagicMock(return_value=self.fake_result(2400, "Login failed"))
        wrapper = EPPLibWrapper()

        with self.assertRaises(LoginError):
            wrapper._create_connection()
        # closed once for the failed login attempt at init, once for the direct call above
        self.assertEqual(mock_client.return_value.close.call_count, 2)

    @less_console_noise_decorator
    @patch("epplibwrapper.client.Client")
    def test_create_connection_login_error_when_close_fails(self, mock_client):
        """A close() failure after a failed login does not mask the LoginError."""
        mock_client.return_value.send = MagicMock(return_value=self.fake_result(2400, "Login failed"))
        mock_client.return_value.close = MagicMock(side_effect=Exception("close failed"))
        wrapper = EPPLibWrapper()

        with self.assertRaises(LoginError):
            wrapper._create_connection()

    @less_console_noise_decorator
    @patch("epplibwrapper.client.Client")
    def test_create_connection_unknown_error(self, mock_client):
        """An unexpected exception while connecting becomes a codeless RegistryError."""
        mock_client.return_value.connect = MagicMock(side_effect=Exception("unknown error"))
        wrapper = EPPLibWrapper()

        with self.assertRaises(RegistryError)as command_response:
            wrapper._create_connection()
        self.assertIsNone(command_response.exception.code)

    @less_console_noise_decorator
    @patch("epplibwrapper.client.Client")
    def test_send_success(self, mock_client):
        """A successful command returns the registry's response."""
        command_success = self.fake_success_result()

        def send_side_effect(command):
            if isinstance(command, commands.Login):
                return self.fake_success_result()
            return command_success

        mock_client.return_value.send = MagicMock(side_effect=send_side_effect)
        wrapper = EPPLibWrapper()

        result = wrapper.send(self.fake_command())

        self.assertIs(result, command_success)
        # 2 because 1 call is made to login at init & 1 call for the fake command
        self.assertEqual(mock_client.return_value.send.call_count, 2)

    @less_console_noise_decorator
    @patch("epplibwrapper.client.Client")
    def test_send_command_rejected_not_retried(self, mock_client):
        """A non-retryable failure code (2303) raises immediately without a retry,
        and the connection goes back to the pool."""

        def send_side_effect(command):
            if isinstance(command, commands.Login):
                return self.fake_success_result()
            return self.fake_result(2303, "Object does not exist")

        mock_client.return_value.send = MagicMock(side_effect=send_side_effect)
        wrapper = EPPLibWrapper()

        with self.assertRaises(RegistryError)as command_response:
            wrapper.send(self.fake_command())

        self.assertEqual(command_response.exception.code, 2303)
        # login at init + one (unretried) command attempt
        self.assertEqual(mock_client.return_value.send.call_count, 2)
        self.assertEqual(wrapper._pool.stats(), {"size": 1, "connections created": 1, "idle": 1, "in use": 0})

    @less_console_noise_decorator
    @patch("epplibwrapper.client.sleep", MagicMock())
    @patch("epplibwrapper.client.Client")
    def test_send_command_failed_retries_and_fails_again(self, mock_client):
        """A retryable failure code (2400) is retried up to 4 attempts, then raised.
        The response did arrive, so the same pooled connection is reused throughout."""

        def send_side_effect(command):
            if isinstance(command, commands.Login):
                return self.fake_success_result()
            return self.fake_result(2400, "Command failed")

        mock_client.return_value.send = MagicMock(side_effect=send_side_effect)
        wrapper = EPPLibWrapper()

        with self.assertRaises(RegistryError)as command_response:
            wrapper.send(self.fake_command())

        self.assertEqual(command_response.exception.code, 2400)
        # login at init + 4 command attempts, all over the same connection
        self.assertEqual(mock_client.return_value.send.call_count, 5)
        mock_client.return_value.connect.assert_called_once()
        mock_client.return_value.close.assert_not_called()

    @less_console_noise_decorator
    @patch("epplibwrapper.client.sleep", MagicMock())
    @patch("epplibwrapper.client.Client")
    def test_send_not_logged_in_prompts_successful_retry(self, mock_client):
        """A 2002 'Registrar is not logged in.' response is retried and can succeed."""
        command_success = self.fake_success_result()
        command_calls = {"count": 0}

        def send_side_effect(command):
            if isinstance(command, commands.Login):
                return self.fake_success_result()
            command_calls["count"] += 1
            if command_calls["count"] == 1:
                return self.fake_result(2002, "Registrar is not logged in.")
            return command_success

        mock_client.return_value.send = MagicMock(side_effect=send_side_effect)
        wrapper = EPPLibWrapper()

        result = wrapper.send(self.fake_command())

        self.assertIs(result, command_success)
        # login at init + failed command + retried command
        self.assertEqual(mock_client.return_value.send.call_count, 3)

    @less_console_noise_decorator
    @patch("epplibwrapper.client.sleep", MagicMock())
    @patch("epplibwrapper.client.Client")
    def test_send_transport_error_reconnects_and_retries_successfully(self, mock_client):
        """A TransportError mid-command discards the connection; the retry gets a
        freshly created (connected + logged in) connection and succeeds."""
        command_success = self.fake_success_result()
        command_calls = {"count": 0}

        def send_side_effect(command):
            if isinstance(command, commands.Login):
                return self.fake_success_result()
            command_calls["count"] += 1
            if command_calls["count"] == 1:
                raise TransportError("connection dropped")
            return command_success

        mock_client.return_value.send = MagicMock(side_effect=send_side_effect)
        wrapper = EPPLibWrapper()

        result = wrapper.send(self.fake_command())

        self.assertIs(result, command_success)
        # initial connection + the replacement built on retry
        self.assertEqual(mock_client.return_value.connect.call_count, 2)
        # the dead connection was closed exactly once
        mock_client.return_value.close.assert_called_once()
        self.assertEqual(wrapper._pool.stats(), {"size": 1, "connections created": 1, "idle": 1, "in use": 0})

    @less_console_noise_decorator
    @patch("epplibwrapper.client.sleep", MagicMock())
    @patch("epplibwrapper.client.Client")
    def test_send_transport_error_exhausts_all_retries(self, mock_client):
        """If every attempt hits a TransportError, all 4 attempts run and the error raises."""

        def send_side_effect(command):
            if isinstance(command, commands.Login):
                return self.fake_success_result()
            raise TransportError("connection dropped")

        mock_client.return_value.send = MagicMock(side_effect=send_side_effect)
        wrapper = EPPLibWrapper()

        with self.assertRaises(RegistryError)as command_response:
            wrapper.send(self.fake_command())

        self.assertEqual(command_response.exception.code, ErrorCode.TRANSPORT_ERROR)
        # initial connection + one replacement per retry attempt
        self.assertEqual(mock_client.return_value.connect.call_count, 4)
        # every dead connection was discarded
        self.assertEqual(mock_client.return_value.close.call_count, 4)
        self.assertEqual(wrapper._pool.stats(), {"size": 1, "connections created": 0, "idle": 0, "in use": 0})

    @less_console_noise_decorator
    @patch("epplibwrapper.client.sleep", MagicMock())
    @patch("epplibwrapper.client.Client")
    def test_send_reconnect_failure_is_retried(self, mock_client):
        """If building the replacement connection itself fails, that failure is also
        retried, and a later successful reconnect completes the command."""
        command_success = self.fake_success_result()
        connect_calls = {"count": 0}
        command_calls = {"count": 0}

        def connect_side_effect():
            connect_calls["count"] += 1
            if connect_calls["count"] == 2:
                raise TransportError("registry unreachable")

        def send_side_effect(command):
            if isinstance(command, commands.Login):
                return self.fake_success_result()
            command_calls["count"] += 1
            if command_calls["count"] == 1:
                raise TransportError("connection dropped")
            return command_success

        mock_client.return_value.connect = MagicMock(side_effect=connect_side_effect)
        mock_client.return_value.send = MagicMock(side_effect=send_side_effect)
        wrapper = EPPLibWrapper()

        result = wrapper.send(self.fake_command())

        self.assertIs(result, command_success)
        # init connect + failed reconnect + successful reconnect
        self.assertEqual(mock_client.return_value.connect.call_count, 3)
        self.assertEqual(wrapper._pool.stats(), {"size": 1, "connections created": 1, "idle": 1, "in use": 0})

    @less_console_noise_decorator
    @patch("epplibwrapper.client.sleep", MagicMock())
    @patch("epplibwrapper.client.Client")
    def test_send_pool_exhausted_raises_registry_error(self, mock_client):
        """When every pooled connection stays checked out, send raises a RegistryError."""
        mock_client.return_value.send = MagicMock(return_value=self.fake_success_result())
        wrapper = EPPLibWrapper()

        # hold the pool's only connection so send() cannot borrow one
        held = wrapper._pool._borrow()
        wrapper._pool.borrow_timeout = 0.01
        try:
            with self.assertRaises(RegistryError)as command_response:
                wrapper.send(self.fake_command())
        finally:
            wrapper._pool._return_connection(held)

        self.assertIn("all pooled EPP connections are busy", str(command_response.exception))

    @less_console_noise_decorator
    @patch("epplibwrapper.client.Client")
    def test_send_parsing_error_raises_registry_error(self, mock_client):
        """A ParsingError is reported as a syntax RegistryError and the connection,
        presumed healthy, is returned to the pool."""

        def send_side_effect(command):
            if isinstance(command, commands.Login):
                return self.fake_success_result()
            raise ParsingError("malformed XML")

        mock_client.return_value.send = MagicMock(side_effect=send_side_effect)
        wrapper = EPPLibWrapper()

        with self.assertRaises(RegistryError) as command_response:
            wrapper._send(self.fake_command())

        self.assertIn("syntax error", str(command_response.exception))
        self.assertEqual(wrapper._pool.stats(), {"size": 1, "connections created": 1, "idle": 1, "in use": 0})

    def fake_failure_send_concurrent_threads(self, command=None):
        """
        Raises a ConcurrentObjectUseError, which gevent throws when accessing
        the same socket from two different threads (greenlets).
        """
        raise ConcurrentObjectUseError("This socket is already used by another thread/greenlet")

    def fake_success_send(self, command=None):
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

    def fake_info_domain_received(self, command=None):
        """
        Simulates receiving a response by reading from a predefined XML file.
        """
        location = Path(__file__).parent / "utility" / "infoDomain.xml"
        xml = (location).read_bytes()
        return xml

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
    @patch("epplibwrapper.client.sleep", MagicMock())
    def test_send_unknown_error_retries_then_recovers(self):
        """
        Validates the resilience of the connection handling mechanism
        during command execution, using a real epplib Client.

        Scenario:
        - Initialization of the pooled connection is successful.
        - An attempt to send a command fails with a ConcurrentObjectUseError.
        - The error is not a transport error, so the connection returns to the pool
          and all retries exhaust with a RegistryError.
        - A subsequent send over the same pooled connection succeeds.
        """
        expected_result = self.get_fake_epp_result()
        tested_command = self.fake_command()
        # Do nothing on _connect: a real connect/login needs a live registry.
        # The real Client + SocketTransport objects are still built and pooled.
        with patch.object(EPPLibWrapper, "_connect"):
            with patch.object(SocketTransport, "send", self.fake_failure_send_concurrent_threads):
                wrapper = EPPLibWrapper()
                with self.assertRaises(RegistryError)as command_response:
                    wrapper.send(tested_command)
                expected_error = "InfoDomain failed to execute due to an unknown error."
                self.assertEqual(command_response.exception.args[0], expected_error)

            # the connection survived (non-transport error) - sending again recovers
            with patch.object(SocketTransport, "send", self.fake_success_send), patch.object(
                SocketTransport, "receive", self.fake_info_domain_received
            ):
                result = wrapper.send(tested_command)
                self.assertEqual(expected_result, result.__dict__)
