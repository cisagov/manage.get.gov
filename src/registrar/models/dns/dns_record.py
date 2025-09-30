from django.db import models
from ..utility.time_stamped_model import TimeStampedModel

class DnsRecord(TimeStampedModel):
    vendor_dns_record = models.ManyToManyField('registrar.VendorDnsRecord',through='DnsRecord_VendorDnsRecord')
