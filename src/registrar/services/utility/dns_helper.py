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
