from django.db import models
from registrar.models.dns.dns_vendor import DnsVendor

DNS_ACCOUNT_NAME_PREFIX = "Account for "  # Must be constant since existing accounts are found by account name
CURRENT_DNS_VENDOR = DnsVendor.CF


class BranchChoices(models.TextChoices):
    EXECUTIVE = "executive", "Executive"
    JUDICIAL = "judicial", "Judicial"
    LEGISLATIVE = "legislative", "Legislative"

    @classmethod
    def get_branch_label(cls, branch_name: str):
        """Returns the associated label for a given org name"""
        return cls(branch_name).label if branch_name else None
