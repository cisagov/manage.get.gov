from django.db.models import ForeignKey, CASCADE
from ..utility.time_stamped_model import TimeStampedModel


class DnsZone_VendorDnsZone(TimeStampedModel):
    dns_zone = ForeignKey("registrar.DnsZone", on_delete=CASCADE, related_name="zone_link")
    vendor_dns_zone = ForeignKey("registrar.VendorDnsZone", on_delete=CASCADE, related_name="zone_link")  # type: ignore
