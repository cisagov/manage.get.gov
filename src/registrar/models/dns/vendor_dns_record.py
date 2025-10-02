from django.db import models
from ..utility.time_stamped_model import TimeStampedModel


class VendorDnsRecord(TimeStampedModel):
    record_xid = models.CharField(max_length=50)  # tbd: current ids have 32 chars
    x_created_at = models.DateTimeField()
    x_updated_at = models.DateTimeField()
