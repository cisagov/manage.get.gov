"""Lookup helper for admin-editable DNS error copy.

See docs/developer/dns-error-handling.md §17. The canonical pattern:

    from registrar.utility.messages import get_user_message

    text = get_user_message("dns", "ZONE_NOT_FOUND")
    # text is None if the DB row is missing or the DB is unreachable;
    # callers MUST fall back to a code-level default in that case.

Cache is invalidated by a post_save / post_delete signal on DnsErrorMessage,
so admin edits in /admin take effect without a process restart.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Process-local cache: (namespace, code) -> message.
# None indicates "not yet loaded". Empty dict indicates "loaded, no rows".
_cache: Optional[dict[tuple[str, str], str]] = None


def _load_cache() -> dict[tuple[str, str], str]:
    # Import inside the function so this module can be imported at Django
    # startup before the app registry is ready.
    from registrar.models.dns.dns_error_message import DnsErrorMessage

    try:
        return {(m.namespace, m.code): m.message for m in DnsErrorMessage.objects.all()}
    except Exception:
        # Table missing, DB down, running during a migration — every caller
        # should handle None and fall back. Don't crash.
        logger.exception("Failed to load DNS error messages; callers will fall back to code-level defaults")
        return {}


def get_user_message(namespace: str, code: str) -> Optional[str]:
    """Return admin-edited message for (namespace, code), or None if absent."""
    global _cache
    if _cache is None:
        _cache = _load_cache()
    return _cache.get((namespace, code))


def invalidate_cache(**_kwargs) -> None:
    """Signal handler / manual invalidation hook."""
    global _cache
    _cache = None
