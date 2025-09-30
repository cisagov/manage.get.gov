from django.db.models import Q, ForeignKey, BooleanField, UniqueConstraint, CASCADE, Model, DateTimeField

class DnsAccount_VendorDnsAccount(Model):
    dns_account = ForeignKey("registrar.DnsAccount", on_delete=CASCADE)
    vendor_dns_account = ForeignKey("registrar.VendorDnsAccount", on_delete=CASCADE)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['is_active'], condition=Q(is_active=True), name='unique_is_active_account')
        ]
