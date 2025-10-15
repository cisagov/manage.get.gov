from django.db.models import ForeignKey, CASCADE
from ..utility.time_stamped_model import TimeStampedModel


class DnsRecord_VendorDnsRecord(TimeStampedModel):
    dns_record = ForeignKey("registrar.DnsRecord", on_delete=CASCADE, related_name="record_link")
    vendor_dns_record = ForeignKey(
        "registrar.VendorDnsRecord", on_delete=CASCADE, related_name="record_link"
    )  # type: ignore
