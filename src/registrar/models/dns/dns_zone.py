from django.db import models

from registrar.models.dns.dns_soa import DnsSoa
from ..utility.time_stamped_model import TimeStampedModel
from django.contrib.postgres.fields import ArrayField

class DnsZone(TimeStampedModel):
    class ZoneModes(models.TextChoices):
        STANDARD = "standard", "Standard"
        CDN_ONLY = "cdn_only", "CDN Only"
        DNS_ONLY = "dns_only", "DNS Only"

    dns_account = models.ForeignKey("DnsAccount", on_delete=models.CASCADE, related_name="zones")

    vendor_dns_zone = models.ManyToManyField(
        "registrar.VendorDnsZone", through="DnsZone_VendorDnsZone", related_name="zones"
    )  # type: ignore

    domain = models.OneToOneField(
        "registrar.Domain", primary_key=True, null=False, on_delete=models.CASCADE
    )  # apex domain

    soa = models.ForeignKey(
        "registrar.DnsSoa",
        on_delete=models.SET_DEFAULT,
        related_name="+",
        default=DnsSoa.get_default_pk)

    name = models.CharField(
        null=True,
        blank=True
    )

    nameservers = ArrayField(
        models.CharField(),
        null=True,
        blank=True
    )

    flatten_all_cnames = models.BooleanField(
        default=False
    )

    foundation_dns = models.BooleanField(
        default=False
    )

    multiprovider = models.BooleanField(
        default=False
    )

    ns_ttl = models.PositiveIntegerField(
        default=86400
    )

    secondary_overrides = models.BooleanField(
        default=False
    )

    zone_mode = models.CharField(
        choices=ZoneModes.choices,
        default="standard"
    )

    def save(self, *args, **kwargs):
        """Save override for custom properties"""
        # Set default zone name to domain name
        if not self.name:
            self.name = self.domain.name
        # Set default SOA to default SOA settings
        if not self.soa:
            self.soa = DnsSoa
        super().save(*args, **kwargs)

