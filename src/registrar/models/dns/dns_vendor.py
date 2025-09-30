from django.db import models
from ..utility.time_stamped_model import TimeStampedModel

class DnsVendor(TimeStampedModel):
    CF = "cloudflare"
    VENDORS = [(CF, "Cloudflare")]
    name = models.CharField(choices=VENDORS, max_length=50)
