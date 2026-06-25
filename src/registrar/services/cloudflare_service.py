from contextlib import contextmanager

from httpx import RequestError, HTTPStatusError
from typing import Any
import logging
from dataclasses import dataclass
from django.conf import settings

from registrar.utility.errors import (
    DnsHostingError,
    DnsHostingErrorCodes,
    DnsValidationError,
    DnsAuthError,
    DnsNotFoundError,
    DnsRateLimitError,
    DnsTransportError,
    DnsUpstreamError,
)

logger = logging.getLogger(__name__)

_STATUS_TO_ERROR = {
    400: (DnsValidationError, DnsHostingErrorCodes.VALIDATION_FAILED),
    401: (DnsAuthError, DnsHostingErrorCodes.AUTH_FAILED),
    403: (DnsAuthError, DnsHostingErrorCodes.AUTH_FAILED),
    404: (DnsNotFoundError, DnsHostingErrorCodes.ZONE_NOT_FOUND),
    409: (DnsValidationError, DnsHostingErrorCodes.RECORD_CONFLICT),
    429: (DnsRateLimitError, DnsHostingErrorCodes.RATE_LIMIT_EXCEEDED),
    500: (DnsUpstreamError, DnsHostingErrorCodes.UPSTREAM_ERROR),
}


def _typed_dns_error(e: HTTPStatusError, **context) -> DnsHostingError:
    """Map an HTTP error to the right DnsHostingError subclass and log once."""
    status = e.response.status_code
    ctx = {"cf_ray": e.response.headers.get("cf-ray"), **context}
    exc_cls, code = _STATUS_TO_ERROR.get(status, (None, None))

    if exc_cls is None and 500 <= status <= 599:
        exc_cls, code = DnsUpstreamError, DnsHostingErrorCodes.UPSTREAM_ERROR
    if exc_cls is None:  # Represents 400s we didn't map to a specific status code
        exc_cls, code = DnsHostingError, DnsHostingErrorCodes.UNKNOWN

    unexpected_code = code == DnsHostingErrorCodes.UNKNOWN
    logger.error(
        "Dns provider returned %s for DNS request",
        status,
        extra={"upstream_status": status, "error_code": code, "response_body": e.response.text, **ctx},
        exc_info=unexpected_code,
    )
    return exc_cls(code=code, upstream_status=status, context=ctx)


@dataclass(frozen=True)
class CloudflareDnsSettingsUpdateResponse:
    """Typed response wrapper for Cloudflare account DNS settings updates."""

    success: bool
    result: dict[str, Any] | None = None
    errors: list[dict[str, Any]] | None = None
    messages: list[dict[str, Any]] | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "CloudflareDnsSettingsUpdateResponse":
        return cls(
            success=bool(data.get("success")),
            result=data.get("result"),
            errors=data.get("errors") or [],
            messages=data.get("messages") or [],
        )


class CloudflareService:
    base_url = "https://api.cloudflare.com/client/v4"
    service_email = settings.SECRET_DNS_SERVICE_EMAIL
    tenant_key = settings.SECRET_DNS_TENANT_KEY
    tenant_id = settings.SECRET_DNS_TENANT_ID
    headers = {
        "X-Auth-Email": service_email,
        "X-Auth-Key": tenant_key,
        "Content-Type": "application/json",
    }

    def __init__(self, client):
        client.base_url = self.base_url
        client.headers = self.headers
        self.client = client

    @contextmanager
    def _dns_call(self, **context):
        """Context manager to catch HTTPX-related errors and convert them into
        appropriate typed DnsHostingErrors."""
        try:
            yield
        except HTTPStatusError as e:
            raise _typed_dns_error(e, **context) from e  # note: `from e` to keep context
        except RequestError as e:
            raise DnsTransportError(
                code=DnsHostingErrorCodes.UPSTREAM_TIMEOUT,
                context={**context, "exc_class": type(e).__name__},
            ) from e

    def create_cf_account(self, account_name: str):
        appended_url = "/accounts"
        data = {"name": account_name, "type": "enterprise", "unit": {"id": self.tenant_id}}
        with self._dns_call(account_name=account_name):
            resp = self.client.post(appended_url, json=data)
            resp.raise_for_status()
            logger.info(f"Created host account {account_name}")

        return resp.json()

    def update_account_dns_settings(
        self,
        account_id: str,
        *,
        zone_mode: str = "dns_only",
        nameservers_type: str = "custom.tenant",
    ) -> CloudflareDnsSettingsUpdateResponse:
        """PATCH /accounts/{account_id}/dns_settings
        Required settings:
        - zone_mode: "standard" | "cdn_only" | "dns_only"
        - type: "cloudflare.standard"
                "cloudflare.standard.random"
                "custom.account"
                "custom.tenant"
        """
        appended_url = f"/accounts/{account_id}/dns_settings"
        data = {
            "zone_defaults": {
                "zone_mode": zone_mode,
                "nameservers": {"type": nameservers_type},
            }
        }

        with self._dns_call(x_account_id=account_id, zone_mode=zone_mode, nameservers_type=nameservers_type):
            resp = self.client.patch(appended_url, json=data)
            resp.raise_for_status()
            logger.info(
                "Updated account DNS settings for account_id=%s (zone_mode=%s, nameservers.type=%s)",
                account_id,
                zone_mode,
                nameservers_type,
            )

        return CloudflareDnsSettingsUpdateResponse.from_json(resp.json())

    def create_cf_zone(self, zone_name: str, x_account_id: str):
        appended_url = "/zones"
        data = {"name": zone_name, "account": {"id": x_account_id}}
        with self._dns_call(x_account_id=x_account_id, zone_name=zone_name):
            resp = self.client.post(appended_url, json=data)
            resp.raise_for_status()
            logger.info(f"Created zone {zone_name}")
        return resp.json()

    def update_zone_dns_settings(
        self, zone_id: str, *, nameservers_type: str = "custom.tenant", ns_set: int = 1
    ) -> CloudflareDnsSettingsUpdateResponse:
        """PATCH /zones/{zone_id}/dns_settings
        Required settings:
        - nameservers_type: "cloudflare.standard"
                "cloudflare.standard.random"
                "custom.account"
                "custom.tenant"
        - ns_set: Min 1, max 5. Default 1 when not passed as argument.
        """
        appended_url = f"/zones/{zone_id}/dns_settings"
        data = {
            "nameservers": {"ns_set": ns_set, "type": nameservers_type},
        }
        with self._dns_call(x_zone_id=zone_id):
            resp = self.client.patch(appended_url, json=data)
            resp.raise_for_status()
            logger.info(
                "Updated zone DNS settings for zone_id=%s (nameservers.type=%s, namservers.ns_set=%s)",
                zone_id,
                nameservers_type,
                ns_set,
            )

        return CloudflareDnsSettingsUpdateResponse.from_json(resp.json())

    def create_dns_record(self, zone_id: str, record_data: dict[str, Any]):
        appended_url = f"/zones/{zone_id}/dns_records"
        with self._dns_call(x_zone_id=zone_id, record_data=record_data):
            resp = self.client.post(appended_url, json=record_data)
            resp.raise_for_status()
            logger.info(f"Created dns record for zone {zone_id}")

        return resp.json()

    def get_account_by_name(self, account_name: str):
        """Fetches a single tenant account by name. Returns the first match or None."""
        appended_url = f"/tenants/{self.tenant_id}/accounts"
        params = {"name": account_name, "page": 1, "per_page": 1}
        with self._dns_call(account_name=account_name):
            logger.info(f"Looking up tenant account by name: {account_name}")
            resp = self.client.get(appended_url, params=params)
            resp.raise_for_status()

        data = resp.json()
        results = data.get("result", [])
        return results[0] if results else None

    def get_account_zones(self, x_account_id: str):
        """Gets all zones under a particular account"""
        appended_url = "/zones"
        params = f"account.id={x_account_id}"
        with self._dns_call(x_account_id=x_account_id):
            logger.info("Getting all of the account's zones")
            resp = self.client.get(appended_url, params=params)
            resp.raise_for_status()

        return resp.json()

    def get_zone_by_id(self, x_zone_id: str):
        """Get zone data given a Clouflare zone id"""
        appended_url = f"/zones/{x_zone_id}"
        with self._dns_call(x_zone_id=x_zone_id):
            logger.info(f"Getting zone data from zone id: {x_zone_id}")
            resp = self.client.get(appended_url)
            resp.raise_for_status()

        logger.info(f"Retrieved zone: {resp}")
        return resp.json()

    def get_dns_record(self, zone_id: str, record_id: str):
        appended_url = f"/zones/{zone_id}/dns_records/{record_id}"
        with self._dns_call(x_zone_id=zone_id, x_record_id=record_id):
            resp = self.client.get(appended_url, headers=self.headers)
            logger.info("Fetching dns record. . .")
            resp.raise_for_status()

        return resp.json()

    def update_dns_record(self, zone_id: str, record_id: str, record_data: dict[str, Any]):
        appended_url = f"/zones/{zone_id}/dns_records/{record_id}"
        with self._dns_call(x_zone_id=zone_id, x_record_id=record_id, record_data=record_data):
            resp = self.client.patch(appended_url, headers=self.headers, json=record_data)
            resp.raise_for_status()
            logger.info(f"Updated dns record {record_id} in zone {zone_id}.")

        return resp.json()

    def delete_dns_record(self, zone_id: str, record_id: str):
        """Delete record given a zone id and record id. Returns result with id of deleted record."""
        appended_url = f"/zones/{zone_id}/dns_records/{record_id}"
        with self._dns_call(x_zone_id=zone_id, x_record_id=record_id):
            resp = self.client.delete(appended_url, headers=self.headers)
            resp.raise_for_status()
            logger.info(f"Deleted dns record {record_id} in zone {zone_id}.")

        return resp.json()
