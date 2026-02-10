from django.db import models
from ..utility.time_stamped_model import TimeStampedModel
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import validate_ipv4_address
from registrar.validations import validate_dns_name


class DnsRecord(TimeStampedModel):
    class RecordTypes(models.TextChoices):
        A = "A", "A"
        AAAA = "AAAA", "AAAA"

    dns_zone = models.ForeignKey("DnsZone", on_delete=models.CASCADE, related_name="records")

    vendor_dns_record = models.ManyToManyField(
        "registrar.VendorDnsRecord", through="DnsRecord_VendorDnsRecord", related_name="records"
    )  # type: ignore

    type = models.CharField(choices=RecordTypes.choices)

    name = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        validators=[validate_dns_name],
    )

    ttl = models.PositiveIntegerField(default=1)

    content = models.CharField(blank=True, null=True)

    comment = models.CharField(blank=True, null=True, max_length=500)

    tags = ArrayField(models.CharField(), null=True, blank=True, default=list)

    def clean(self):
        super().clean()

        errors = {}

        # TTL must be between 60 and 86400.
        # If we add proxy field to records in the future, we can also allow TTL=1 as below:
        # if self.ttl == 1: return self.proxy
        if self.ttl < 60 or self.ttl > 86400:
            errors["ttl"] = ["TTL for unproxied records must be between 60 and 86400."]

        # A record-specific validation
        if self.type == self.RecordTypes.A and self.content:
            try:
                validate_ipv4_address(self.content)
            except ValidationError as e:
                errors["content"] = e.messages

        if errors:
            raise ValidationError(errors)
