"""Shared httpx client for DNS vendor calls.
Centralizes the timeout and retry policy.
See docs/developer/dns-error-handling.md, "Network Timeouts & Retries".
"""

import logging
import time
import httpx
from registrar.utility.errors import DnsHostingErrorCodes, DnsTransportError

logger = logging.getLogger(__name__)

# Per-request timeouts in secs, short connect timeout to trigger retries sooner.
DNS_TIMEOUT = httpx.Timeout(connect=3, read=10, write=10, pool=5)

CONNECT_RETRIES = 2

RETRYABLE_METHODS = frozenset({"GET", "HEAD"})

MAX_ATTEMPTS = 2

# Cloudflare returns 429 for rate limits.
RATE_LIMITED_STATUS = 429

# Base backoff seconds is doubled with each attempt, so we cap it.
BACKOFF_BASE_SECONDS = 1
MAX_BACKOFF_SECONDS = 5


def _is_retryable_status(status_code):
    """A 429 or any 5xx is worth retrying for a read-only request."""
    return status_code == RATE_LIMITED_STATUS or 500 <= status_code <= 599


def _backoff_seconds(response, attempt):
    """Seconds to wait before the next attempt, honoring Retry-After on a 429."""
    if response is not None and response.status_code == RATE_LIMITED_STATUS:
        retry_after = response.headers.get("retry-after", "")
        if retry_after.isdigit():
            return min(int(retry_after), MAX_BACKOFF_SECONDS)
    return min(BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)), MAX_BACKOFF_SECONDS)


class RetryTransport(httpx.HTTPTransport):
    """Retries reads on transient failures; runs writes once to avoid duplicate records."""

    def handle_request(self, request):
        if request.method not in RETRYABLE_METHODS:
            return self._single_attempt(request)

        for attempt in range(1, MAX_ATTEMPTS + 1):
            is_last_attempt = attempt == MAX_ATTEMPTS
            try:
                response = super().handle_request(request)
            except httpx.RequestError as error:
                if is_last_attempt:
                    raise self._transport_error(request, error) from error
                time.sleep(_backoff_seconds(None, attempt))
                continue

            if not is_last_attempt and _is_retryable_status(response.status_code):
                wait = _backoff_seconds(response, attempt)
                response.close()
                time.sleep(wait)
                continue
            return response

    def _single_attempt(self, request):
        """Run a write once and translate a missing response into DnsTransportError."""
        try:
            return super().handle_request(request)
        except httpx.RequestError as error:
            raise self._transport_error(request, error) from error

    def _transport_error(self, request, error):
        logger.error("DNS request to %s failed with no response: %s", request.url, error)
        return DnsTransportError(
            code=DnsHostingErrorCodes.UPSTREAM_TIMEOUT,
            context={"method": request.method, "exc_class": type(error).__name__},
        )


def build_dns_client():
    """Build the shared httpx client for Cloudflare DNS calls with timeout and retries."""
    transport = RetryTransport(retries=CONNECT_RETRIES)
    return httpx.Client(timeout=DNS_TIMEOUT, transport=transport)
