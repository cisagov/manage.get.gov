from django.db import models
from ..utility.time_stamped_model import TimeStampedModel


class DnsAccount(TimeStampedModel):
    name = models.CharField(unique=True, max_length=255)
    vendor_dns_account = models.ManyToManyField(
        "registrar.VendorDnsAccount", through="DnsAccount_VendorDnsAccount", related_name="accounts"
    )  # type: ignore

    @property
    def x_account_id(self):
        link = self.account_link.filter(is_active=True).select_related("vendor_dns_account").first()

        return link.vendor_dns_account.x_account_id if link else None
