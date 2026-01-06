from django.db import models
from ..utility.time_stamped_model import TimeStampedModel


class VendorDnsAccount(TimeStampedModel):
    dns_vendor = models.ForeignKey(
        "registrar.DnsVendor", null=False, blank=False, on_delete=models.CASCADE, related_name="vendor_accounts"
    )
    x_account_id = models.CharField(
        max_length=32,
        unique=True
    )  # tbd: current ids have 32 chars
    x_created_at = models.DateTimeField()
    x_updated_at = models.DateTimeField()
