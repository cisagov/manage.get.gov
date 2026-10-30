"""DNS utility functions for naming conventions and vendor integration.

This module provides helper functions for DNS-related tasks, primarily for
naming conventions used with external vendor integration (see DnsHostService).

Database lookups use model methods (e.g., DnsZone.get_zone_id_for_domain).
"""

from registrar.utility.constants import DNS_ACCOUNT_NAME_PREFIX


def make_dns_account_name(domain_name) -> str:
    """Create a standard format account name for dns vendor account.

    Used when provisioning new DNS vendor accounts to ensure consistent naming.
    """
    return DNS_ACCOUNT_NAME_PREFIX + domain_name


def get_dns_zone_name_from_account_name(account_name) -> str:
    if not account_name.startswith(DNS_ACCOUNT_NAME_PREFIX):
        raise ValueError(
            f"Account name {account_name!r} does not start with " f"expected prefix {DNS_ACCOUNT_NAME_PREFIX!r}"
        )

    zone_name = account_name[len(DNS_ACCOUNT_NAME_PREFIX) :]

    return zone_name
