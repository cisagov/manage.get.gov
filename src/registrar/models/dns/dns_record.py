from django.db import models
from ..utility.time_stamped_model import TimeStampedModel
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError


class DnsRecord(TimeStampedModel):
    class RecordTypes(models.TextChoices):
        A = "a", "A"

    dns_zone = models.ForeignKey("DnsZone", on_delete=models.CASCADE, related_name="records")

    vendor_dns_record = models.ManyToManyField(
        "registrar.VendorDnsRecord", through="DnsRecord_VendorDnsRecord", related_name="records"
    )  # type: ignore

    type = models.CharField(choices=RecordTypes.choices, default="a")

    name = models.CharField(max_length=255, blank=True, null=True)

    ttl = models.PositiveIntegerField(default=1)

    content = models.CharField(blank=True, null=True)

    comment = models.CharField(blank=False, null=False)

    tags = ArrayField(models.CharField(), null=True, blank=True, default=list)

    def save(self, *args, **kwargs):
        """Save override for custom properties"""
        # Set default record name to zone's domain name.
        # Some DNS records make name optional but A records require a name.

        # Setting record name to @ indicates it is for root domain
        if not self.name:
            self.name = "@"
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        # TTL must be between 60 and 86400.
        # If we add proxy field to records in the future, we can also allow TTL=1 as below:
        # if self.ttl == 1: return self.proxy
        if self.ttl < 60 or self.ttl > 84600:
            return ValidationError({"ttl": "TTL for unproxied records must be between 60 and 86400."})
