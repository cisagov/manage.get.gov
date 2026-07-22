import httpx
import respx
from unittest import mock
from django.test import SimpleTestCase

from registrar.services.dns_http_client import DNS_TIMEOUT, MAX_ATTEMPTS, RetryTransport, build_dns_client
from registrar.services.mock_cloudflare_service import MockCloudflareService
from registrar.utility.errors import DnsHostingErrorCodes, DnsTransportError


class TestDnsHttpClient(SimpleTestCase):
    """Timeout and retry policy for the shared DNS httpx client."""

    base_url = "https://api.cloudflare.com/client/v4"

    def setUp(self):
        # The app starts a shared mock at boot that grabs all DNS requests.
        # Turn it off so this test's fake responses are used.
        self.global_mock = MockCloudflareService()
        self._mock_was_active = self.global_mock.is_active
        if self._mock_was_active:
            self.global_mock.stop()

    def tearDown(self):
        if self._mock_was_active:
            self.global_mock.start()

    @respx.mock
    @mock.patch("registrar.services.dns_http_client.time.sleep")
    def test_get_retries_429_with_retry_after_then_succeeds(self, mock_sleep):
        """A 429 with Retry-After retries the GET once and then succeeds."""
        url = f"{self.base_url}/zones/abc"
        route = respx.get(url).mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "1"}, json={}),
                httpx.Response(200, json={"success": True}),
            ]
        )

        with build_dns_client() as client:
            response = client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(route.call_count, 2)
        mock_sleep.assert_called_once_with(1)

    @respx.mock
    @mock.patch("registrar.services.dns_http_client.time.sleep")
    def test_get_retries_5xx_then_succeeds(self, mock_sleep):
        """A 5xx retries the GET once and then succeeds."""
        url = f"{self.base_url}/zones/abc"
        route = respx.get(url).mock(
            side_effect=[
                httpx.Response(503, json={}),
                httpx.Response(200, json={"success": True}),
            ]
        )

        with build_dns_client() as client:
            response = client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(route.call_count, 2)

    @respx.mock
    @mock.patch("registrar.services.dns_http_client.time.sleep")
    def test_get_returns_last_error_when_retries_exhausted(self, mock_sleep):
        """A GET that keeps failing stops after the capped number of attempts."""
        url = f"{self.base_url}/zones/abc"
        route = respx.get(url).mock(return_value=httpx.Response(503, json={}))

        with build_dns_client() as client:
            response = client.get(url)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(route.call_count, MAX_ATTEMPTS)

    @respx.mock
    @mock.patch("registrar.services.dns_http_client.time.sleep")
    def test_post_500_fails_on_single_attempt(self, mock_sleep):
        """A POST that returns 500 is not retried."""
        url = f"{self.base_url}/zones/abc/dns_records"
        route = respx.post(url).mock(return_value=httpx.Response(500, json={}))

        with build_dns_client() as client:
            response = client.post(url, json={})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(route.call_count, 1)
        mock_sleep.assert_not_called()

    @respx.mock
    @mock.patch("registrar.services.dns_http_client.time.sleep")
    def test_connect_timeout_surfaces_as_dns_transport_error(self, mock_sleep):
        """A connect timeout with no response surfaces as DnsTransportError."""
        url = f"{self.base_url}/zones/abc"
        respx.get(url).mock(side_effect=httpx.ConnectTimeout("hung"))

        with build_dns_client() as client:
            with self.assertRaises(DnsTransportError) as context:
                client.get(url)

        self.assertEqual(context.exception.code, DnsHostingErrorCodes.UPSTREAM_TIMEOUT)

    @respx.mock
    @mock.patch("registrar.services.dns_http_client.time.sleep")
    def test_write_connect_timeout_surfaces_as_dns_transport_error(self, mock_sleep):
        """A write that hits a network failure also surfaces as DnsTransportError."""
        url = f"{self.base_url}/zones/abc/dns_records"
        route = respx.post(url).mock(side_effect=httpx.ConnectError("no route"))

        with build_dns_client() as client:
            with self.assertRaises(DnsTransportError):
                client.post(url, json={})

        # Writes never retry, so only one attempt is made.
        self.assertEqual(route.call_count, 1)

    def test_build_dns_client_applies_timeout_and_retry_transport(self):
        """The factory wires up the shared timeout and retry transport."""
        client = build_dns_client()
        try:
            self.assertEqual(client.timeout, DNS_TIMEOUT)
            self.assertIsInstance(client._transport, RetryTransport)
        finally:
            client.close()
