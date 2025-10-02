from django.db.models import Q, ForeignKey, BooleanField, UniqueConstraint, CASCADE
from ..utility.time_stamped_model import TimeStampedModel

class DnsZone_VendorDnsZone(TimeStampedModel):
    dns_zone = ForeignKey("registrar.DnsZone", on_delete=CASCADE)
    vendor_dns_zone = ForeignKey("registrar.VendorDnsZone", on_delete=CASCADE)
    is_active = BooleanField(default=True)

    class Meta:
        constraints = [
            UniqueConstraint(fields=["is_active"], condition=Q(is_active=True), name="unique_is_active_zone")
        ]
