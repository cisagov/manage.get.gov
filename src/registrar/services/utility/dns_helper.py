from registrar.utility.constants import DNS_ACCOUNT_NAME_PREFIX


def make_dns_account_name(domain_name) -> str:
    """Create a standard format account name for dns vendor account"""
    return DNS_ACCOUNT_NAME_PREFIX + domain_name
