"""Admin-editable user-facing copy for DNS-hosting errors.

Replaces the spreadsheet-per-column workflow: design/product edit the `message`
field in /admin and the change takes effect immediately (no deploy) via a
post_save signal that invalidates the in-process cache.

The code-level `_error_mapping` dict in utility/errors.py remains as the
FALLBACK used when a DB row is missing or the DB is unreachable — never a hard
dependency. See docs/developer/dns-error-handling.md.
"""

from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver


class DnsErrorMessage(models.Model):
    """User-facing copy for one DNS error code. Admin-editable."""

    namespace = models.CharField(
        max_length=32,
        default="dns",
        help_text="Future-proof grouping. v1 ships only the 'dns' namespace.",
    )
    code = models.CharField(
        max_length=64,
        help_text="Matches DnsHostingErrorCodes member name, e.g. ZONE_NOT_FOUND.",
    )
    message = models.TextField(help_text="What the user will see.")
    internal_notes = models.TextField(
        blank=True,
        default="",
        help_text="Context for editors: where does this appear? What triggers it?",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["namespace", "code"],
                name="dns_error_message_unique_namespace_code",
            ),
        ]
        verbose_name = "DNS error message"
        verbose_name_plural = "DNS error messages"
        ordering = ("namespace", "code")

    def __str__(self):
        return f"{self.namespace}.{self.code}"


@receiver([post_save, post_delete], sender=DnsErrorMessage)
def _invalidate_message_cache(sender, **kwargs):
    # Local import avoids a circular reference at Django startup.
    from registrar.utility.messages import invalidate_cache

    invalidate_cache()
