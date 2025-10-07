from django.db import models
from ..utility.time_stamped_model import TimeStampedModel


class DnsZone(TimeStampedModel):
    dns_account = models.ForeignKey("DnsAccount", on_delete=models.CASCADE)
    vendor_dns_zone = models.ManyToManyField("registrar.VendorDnsZone", through="DnsZone_VendorDnsZone")  # type: ignore
    domain = models.ForeignKey("registrar.Domain", null=False, blank=False, on_delete=models.CASCADE)
