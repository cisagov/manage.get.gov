"""Bounded, admin-visible audit trail of DNS-hosting operations.

Each row captures one invocation of a DNS-facing operation (create/update
record, enroll domain, etc.) with enough structured metadata for support and
analysts to correlate a user-reported `request_id` to the upstream Cloudflare
call — without SSO-ing into OpenSearch.

This is NOT a log replacement. It is a bounded admin-UI surface with its own
retention policy (TTL'd, target 30 days). Full tracebacks continue to live in
OpenSearch.

See docs/developer/dns-error-handling.md and
docs/developer/dns-error-handling.md for the full design.
"""

from django.db import models


class DnsOperationLog(models.Model):
    """Admin-visible audit trail of DNS hosting operations."""

    class Operation(models.TextChoices):
        CREATE_DNS_RECORD = "create_dns_record", "Create DNS record"
        UPDATE_DNS_RECORD = "update_dns_record", "Update DNS record"
        ENROLL_DOMAIN = "enroll_domain", "Enroll domain in DNS hosting"

    class Outcome(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILURE = "failure", "Failure"

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user_email = models.CharField(max_length=255, blank=True, default="")
    request_id = models.CharField(max_length=64, blank=True, default="", db_index=True)

    operation = models.CharField(max_length=64, choices=Operation.choices)
    outcome = models.CharField(max_length=16, choices=Outcome.choices)

    domain_name = models.CharField(max_length=255, blank=True, default="", db_index=True)
    dns_account_id = models.CharField(max_length=255, blank=True, default="")
    zone_id = models.CharField(max_length=255, blank=True, default="")
    record_id = models.CharField(max_length=255, blank=True, default="")

    error_code = models.CharField(max_length=64, blank=True, default="")
    upstream_status = models.IntegerField(null=True, blank=True)
    cf_ray = models.CharField(max_length=255, blank=True, default="")
    duration_ms = models.IntegerField(null=True, blank=True)

    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("-timestamp",)
        verbose_name = "DNS operation log entry"
        verbose_name_plural = "DNS operation log"

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} {self.operation} {self.outcome} {self.domain_name}"
