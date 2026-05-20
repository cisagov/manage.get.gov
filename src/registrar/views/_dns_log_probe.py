"""Admin-only probe — exercises the real DNS error path so we can see what `logs-app*` captures."""

import logging

from django.http import JsonResponse
from httpx import Client, RequestError

from registrar.services.cloudflare_service import CloudflareService
from registrar.utility.errors import DnsHostingError

logger = logging.getLogger(__name__)


def dns_log_probe(request):
    bogus_zone_id = "probe-zone-id-does-not-exist"
    record_data = {
        "name": "error-400-probe",
        "type": "A",
        "content": "192.0.2.1",
        "ttl": 3600,
        "comment": "dns_log_probe",
    }

    client = Client()
    service = CloudflareService(client)

    try:
        service.create_dns_record(zone_id=bogus_zone_id, record_data=record_data)
    except (DnsHostingError, RequestError, Exception) as exc:
        logger.exception("DNS log probe fired", extra={"probe_marker": "dns_log_probe"})
        return JsonResponse(
            {
                "status": "probe_fired",
                "exception_class": type(exc).__name__,
                "exception_message": str(exc),
                "search": "logs-app*  ➜  probe_marker:dns_log_probe",
            }
        )
    finally:
        client.close()

    return JsonResponse({"status": "no_exception_raised"})
