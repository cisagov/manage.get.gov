from django.db import models
from ..utility.time_stamped_model import TimeStampedModel


class DnsAccount(TimeStampedModel):
    name = models.CharField(unique=True, max_length=255)
    vendor_dns_account = models.ManyToManyField("registrar.VendorDnsAccount", through="DnsAccount_VendorDnsAccount")
