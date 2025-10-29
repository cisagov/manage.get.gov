from django.db import models
from django.db.models import ForeignKey, CASCADE, UniqueConstraint, Q
from ..utility.time_stamped_model import TimeStampedModel


class DnsRecord_VendorDnsRecord(TimeStampedModel):
    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["dns_record"], condition=Q(is_active=True), name="unique_active_vendor_record_per_dns_record"
            )
        ]

    dns_record = ForeignKey("registrar.DnsRecord", on_delete=CASCADE, related_name="record_link")

    vendor_dns_record = ForeignKey(
        "registrar.VendorDnsRecord", on_delete=CASCADE, related_name="record_link"
    )  # type: ignore

    is_active = models.BooleanField(default=True)