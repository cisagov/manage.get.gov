from django.db import models
from django.db.models import UniqueConstraint, Q
from ..utility.time_stamped_model import TimeStampedModel


class VendorDnsAccount(TimeStampedModel):
    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["dns_vendor", "x_account_id"], name="unique_vendor_dns_account_per_dns_vendor"
            )
        ]

    dns_vendor = models.ForeignKey(
        "registrar.DnsVendor", null=False, blank=False, on_delete=models.CASCADE, related_name="vendor_accounts"
    )
    x_account_id = models.CharField(max_length=32)
    x_created_at = models.DateTimeField()
    x_updated_at = models.DateTimeField()
