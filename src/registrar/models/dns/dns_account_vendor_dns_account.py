from django.db import models
from django.db.models import Q, UniqueConstraint
from ..utility.time_stamped_model import TimeStampedModel


class DnsAccount_VendorDnsAccount(TimeStampedModel):
    dns_account = models.ForeignKey("registrar.DnsAccount", on_delete=models.CASCADE, related_name="account_link")
    vendor_dns_account = models.ForeignKey(
        "registrar.VendorDnsAccount", on_delete=models.CASCADE, related_name="account_link"
    )  # type: ignore
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["dns_account"],
                condition=Q(is_active=True),
                name="unique_active_vendor_per_dns_account",
            ),
        ]
