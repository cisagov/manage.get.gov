import logging

from django.db import models
from ..utility.time_stamped_model import TimeStampedModel
from registrar.models.dns.dns_account_vendor_dns_account import DnsAccount_VendorDnsAccount

logger = logging.getLogger(__name__)


class DnsAccount(TimeStampedModel):
    name = models.CharField(unique=True, max_length=255)
    vendor_dns_account = models.ManyToManyField(
        "registrar.VendorDnsAccount", through="DnsAccount_VendorDnsAccount", related_name="accounts"
    )  # type: ignore

    @property
    def x_account_id(self):
        try:
            x_account_id = self.account_link.get(is_active=True).vendor_dns_account.x_account_id
        except DnsAccount_VendorDnsAccount.DoesNotExist:
            logger.error(f"There is a database entry but no active vendor for this account {self.name}")
            raise

        return x_account_id
