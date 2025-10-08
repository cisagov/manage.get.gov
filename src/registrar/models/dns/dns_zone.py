from django.db import models
from ..utility.time_stamped_model import TimeStampedModel


class DnsZone(TimeStampedModel):
    dns_account = models.ForeignKey("DnsAccount", on_delete=models.CASCADE, related_name="zones")
    vendor_dns_zone = models.ManyToManyField(
        "registrar.VendorDnsZone", through="DnsZone_VendorDnsZone", related_name="zones"
    )  # type: ignore
    domain = models.OneToOneField("registrar.Domain", primary_key=True, null=False, on_delete=models.CASCADE)
