from django.db.models import Q, ForeignKey, BooleanField, UniqueConstraint, CASCADE, Model, DateTimeField
from ..utility.time_stamped_model import TimeStampedModel

class DnsAccount_VendorDnsAccount(TimeStampedModel):
    dns_account = ForeignKey("registrar.DnsAccount", on_delete=CASCADE)
    vendor_dns_account = ForeignKey("registrar.VendorDnsAccount", on_delete=CASCADE)
    is_active = BooleanField(default=True)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['is_active'], condition=Q(is_active=True), name='unique_is_active_account')
        ]
