from django.db import models
from ..utility.time_stamped_model import TimeStampedModel


class DnsRecord(TimeStampedModel):
    dns_zone = models.ForeignKey("DnsZone", on_delete=models.CASCADE)
    vendor_dns_record = models.ManyToManyField("registrar.VendorDnsRecord", through="DnsRecord_VendorDnsRecord")
