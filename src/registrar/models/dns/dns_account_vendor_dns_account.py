from django.db.models import Q, UniqueConstraint, ForeignKey, BooleanField, CASCADE
from ..utility.time_stamped_model import TimeStampedModel


class DnsAccount_VendorDnsAccount(TimeStampedModel):
    dns_account = ForeignKey("registrar.DnsAccount", on_delete=CASCADE, related_name="account_link")
    vendor_dns_account = ForeignKey(
        "registrar.VendorDnsAccount", on_delete=CASCADE, related_name="account_link"
    )  # type: ignore
    is_active = BooleanField(default=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["dns_account"],
                condition=Q(is_active=True),
                name="unique_active_vendor_account_per_dns_account",
            ),
        ]
