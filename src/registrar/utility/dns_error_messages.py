"""User-facing DNS hosting error copy and the view-layer resolver that turns a
:class:`registrar.utility.errors.DnsHostingError` into per-form-field messages.

The copy constants mirror the "⭐ Revised / New alert message" column of the DNS
Hosting error messages spreadsheet (see ticket #4672).

TODO(#4893/#4932): When the admin-editable ``DnsErrorMessage`` table from PR #4932
lands, replace these constants with DB lookups (and keep the constants as fallback
defaults so a missing row never 500s).
"""

from registrar.utility.errors import (
    DnsContentLengthExceededError,
    DnsDuplicateRecordError,
    DnsHostingError,
    DnsNameConflictError,
)

# User-facing copy — ticket #4672 AC.
DNS_DUPLICATE_RECORD_ERROR_MESSAGE = "You already entered this DNS record. DNS records must be unique."
DNS_CNAME_CONFLICT_ON_A_AAAA_ERROR_MESSAGE = "A CNAME record with that name already exists."
DNS_A_AAAA_CONFLICT_ON_CNAME_ERROR_MESSAGE = "An A or AAAA record with that name already exists."
DNS_TXT_LENGTH_LIMIT_ERROR_MESSAGE = (
    "Combined content length of records with this name and type must not exceed 8192 characters."
)
DNS_GENERIC_VALIDATION_ERROR_MESSAGE = "We couldn't save this DNS record. Please review and try again."


def resolve_dns_error_messages(error: DnsHostingError) -> dict[str, list[str]]:
    """Map a :class:`DnsHostingError` to form-field-keyed user messages.

    Keys are form field names (``"name"``, ``"content"``) or ``"__all__"`` for
    non-field errors. Values are lists of message strings suitable for
    ``form.add_error(field, message)``.
    """
    if isinstance(error, DnsContentLengthExceededError):
        return {"content": [DNS_TXT_LENGTH_LIMIT_ERROR_MESSAGE]}

    if isinstance(error, DnsDuplicateRecordError):
        return {"__all__": [DNS_DUPLICATE_RECORD_ERROR_MESSAGE]}

    if isinstance(error, DnsNameConflictError):
        rtype = (error.submitted_record_type or "").upper()
        if rtype == "CNAME":
            return {"name": [DNS_A_AAAA_CONFLICT_ON_CNAME_ERROR_MESSAGE]}
        return {"name": [DNS_CNAME_CONFLICT_ON_A_AAAA_ERROR_MESSAGE]}

    # Fallback: surface the vendor's own message if we have one, otherwise a generic copy.
    vendor_message = str(error) if str(error) else None
    return {"__all__": [vendor_message or DNS_GENERIC_VALIDATION_ERROR_MESSAGE]}
