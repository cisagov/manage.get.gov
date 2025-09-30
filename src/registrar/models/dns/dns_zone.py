from django.db import models
from ..utility.time_stamped_model import TimeStampedModel

class DnsZone(TimeStampedModel):
    # name = models.CharField(max_length=253) # must match domain name? or just reference to Domain?
    vendor_dns_zone = models.ManyToManyField('registrar.VendorDnsZone',through='DnsZone_VendorDnsZone')
    domain = models.ForeignKey("registrar.Domain", null=False, blank=False, on_delete=models.CASCADE)
