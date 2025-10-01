from django.db.models import Q, ForeignKey, BooleanField, UniqueConstraint, CASCADE, Model, DateTimeField
from ..utility.time_stamped_model import TimeStampedModel


class DnsRecord_VendorDnsRecord(Model):
    dns_record = ForeignKey("registrar.DnsRecord", on_delete=CASCADE)
    vendor_dns_record = ForeignKey("registrar.VendorDnsRecord", on_delete=CASCADE)
    is_active = BooleanField(default=True)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['is_active'], condition=Q(is_active=True), name='unique_is_active_record')
        ]
