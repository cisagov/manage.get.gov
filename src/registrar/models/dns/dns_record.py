from django.db import models
from ..utility.time_stamped_model import TimeStampedModel
from django.core.validators import MaxValueValidator, MinValueValidator
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError

class DnsRecord(TimeStampedModel):
    def validate_ttl(ttl):
        if ttl != 1 and (ttl < 60 or ttl > 86400):
            raise ValidationError(
                "TTL must be 1 (automatic) or a number between 60 and 86400."
            )

    class RecordTypes(models.TextChoices):
        A = "a", "A"

    dns_zone = models.ForeignKey("DnsZone", on_delete=models.CASCADE, related_name="records")

    vendor_dns_record = models.ManyToManyField(
        "registrar.VendorDnsRecord", through="DnsRecord_VendorDnsRecord", related_name="records"
    )  # type: ignore

    type = models.CharField(choices=RecordTypes.choices, default="a")

    name = models.CharField(max_length=255, blank=True, null=True)

    ttl = models.PositiveIntegerField(
        default=1, validators=[validate_ttl]
    )

    content = models.CharField(blank=True, null=True)

    comment = models.CharField(blank=True, null=True)

    tags = ArrayField(models.CharField(), null=True, blank=True, default=[])

    priority = models.PositiveIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(65535)]
    )

    def save(self, *args, **kwargs):
        """Save override for custom properties"""
        # Set default record name to zone's domain name.
        # Some DNS records make name optional but A records require a name.
        if not self.name:
            self.name = self.dns_zone.domain.name
        super().save(*args, **kwargs)
