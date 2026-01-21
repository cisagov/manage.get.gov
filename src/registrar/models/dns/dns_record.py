from django.db import models
from ..utility.time_stamped_model import TimeStampedModel
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import validate_ipv4_address
from registrar.validations import validate_dns_name


class DnsRecord(TimeStampedModel):
    class RecordTypes(models.TextChoices):
        A = "a", "A"

    dns_zone = models.ForeignKey("DnsZone", on_delete=models.CASCADE, related_name="records")

    vendor_dns_record = models.ManyToManyField(
        "registrar.VendorDnsRecord", through="DnsRecord_VendorDnsRecord", related_name="records"
    )  # type: ignore

    type = models.CharField(choices=RecordTypes.choices, default="a")

    name = models.CharField(max_length=255, blank=False, null=False, default="@")

    ttl = models.PositiveIntegerField(default=1)

    content = models.CharField(blank=True, null=True)

    comment = models.CharField(blank=True, null=True)

    tags = ArrayField(models.CharField(), null=True, blank=True, default=list)

    def clean(self):
        super().clean()

        # TTL must be between 60 and 86400.
        # If we add proxy field to records in the future, we can also allow TTL=1 as below:
        # if self.ttl == 1: return self.proxy
        if self.ttl < 60 or self.ttl > 84600:
            raise ValidationError({"ttl": "TTL for unproxied records must be between 60 and 86400."})

        # DNS Record name validation. This will apply for A, AAAA, and CNAME record types.
        if self.name != "@":
            validate_dns_name(self.name)

        # A record-specific validation
        if self.type == self.RecordTypes.A:
            if not self.content:
                raise ValidationError({"content": "IPv4 address is required for A records."})

            validate_ipv4_address(self.content)
