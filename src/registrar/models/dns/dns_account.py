import logging

from django.db import models
from ..utility.time_stamped_model import TimeStampedModel
from registrar.models.dns.dns_account_vendor_dns_account import DnsAccount_VendorDnsAccount as AccountsJoin

logger = logging.getLogger(__name__)


class DnsAccount(TimeStampedModel):
    name = models.CharField(unique=True, max_length=255)
    vendor_dns_account = models.ManyToManyField(
        "registrar.VendorDnsAccount", through="DnsAccount_VendorDnsAccount", related_name="accounts"
    )  # type: ignore

    def get_active_x_account_id(self):
        try:
            x_account_id = self.account_link.get(is_active=True).vendor_dns_account.x_account_id
        # TODO: Revisit how we handle DoesNotExist when we are transitioning to a different vendor
        except AccountsJoin.DoesNotExist:
            """
            With `is_active` set to True by default, this would not be reachable unless we switched vendors
            and did not yet set up a vendor_dns_account for the new vendor as active
            """
            logger.info(f"There is a database entry but no active vendor for this account {self.name}")
            return None

        return x_account_id
