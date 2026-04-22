"""Seed the 8 DnsHostingErrorCodes rows into DnsErrorMessage.

Uses get_or_create so re-running is safe and admin edits are never overwritten.
See docs/developer/dns-error-handling.md §17.6.
"""

from django.db import migrations

SEED_MESSAGES = [
    (
        "ZONE_NOT_FOUND",
        "We couldn’t find the DNS zone for this domain. It may not be enrolled in DNS hosting yet.",
        "Shown when Cloudflare returns 404 for a zone operation.",
    ),
    (
        "RECORD_CONFLICT",
        "A record with that name and type already exists.",
        "Cloudflare returned 409; user tried to create a duplicate record.",
    ),
    (
        "VALIDATION_FAILED",
        "The DNS record couldn’t be saved because one of its fields wasn’t valid.",
        "Cloudflare returned 400 for a record create/update.",
    ),
    (
        "RATE_LIMIT_EXCEEDED",
        "You’re making changes too quickly. Please wait a moment and try again.",
        "Cloudflare returned 429.",
    ),
    (
        "AUTH_FAILED",
        "We couldn’t reach our DNS provider. Please try again in a moment.",
        "Cloudflare returned 401/403 — auth credentials broken. Pages oncall.",
    ),
    (
        "UPSTREAM_TIMEOUT",
        "We couldn’t reach our DNS provider. Please try again in a moment.",
        "httpx timeout / network failure reaching Cloudflare.",
    ),
    (
        "UPSTREAM_ERROR",
        "We couldn’t reach our DNS provider. Please try again in a moment.",
        "Cloudflare returned 5xx.",
    ),
    (
        "UNKNOWN",
        "Something went wrong while updating DNS. Please try again in a moment.",
        "Unexpected upstream status; triage required to promote to a named code.",
    ),
]


def seed_messages(apps, schema_editor):
    DnsErrorMessage = apps.get_model("registrar", "DnsErrorMessage")
    for code, message, notes in SEED_MESSAGES:
        DnsErrorMessage.objects.get_or_create(
            namespace="dns",
            code=code,
            defaults={"message": message, "internal_notes": notes},
        )


def unseed_messages(apps, schema_editor):
    DnsErrorMessage = apps.get_model("registrar", "DnsErrorMessage")
    DnsErrorMessage.objects.filter(namespace="dns", code__in=[c for c, _, _ in SEED_MESSAGES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("registrar", "0179_dns_error_message"),
    ]

    operations = [
        migrations.RunPython(seed_messages, unseed_messages),
    ]
