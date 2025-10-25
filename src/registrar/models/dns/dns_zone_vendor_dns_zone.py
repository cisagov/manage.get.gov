from django.db.models import ForeignKey, BooleanField, CASCADE, UniqueConstraint, Q
from ..utility.time_stamped_model import TimeStampedModel


class DnsZone_VendorDnsZone(TimeStampedModel):
    class Meta:
        constraints = [
            UniqueConstraint(fields=["dns_zone"], condition=Q(is_active=True), name="unique_active_vendor_per_dns_zone")
        ]

    dns_zone = ForeignKey("registrar.DnsZone", on_delete=CASCADE, related_name="zone_link")
    vendor_dns_zone = ForeignKey("registrar.VendorDnsZone", on_delete=CASCADE, related_name="zone_link")  # type: ignore
    is_active = BooleanField(default=True)
