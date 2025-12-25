import logging

from django.db import models

from registrar.models.dns.dns_soa import DnsSoa
from registrar.models.dns.dns_zone_vendor_dns_zone import DnsZone_VendorDnsZone as ZonesLink
from ..utility.time_stamped_model import TimeStampedModel
from django.contrib.postgres.fields import ArrayField

logger = logging.getLogger(__name__)


class DnsZone(TimeStampedModel):
    class ZoneModes(models.TextChoices):
        STANDARD = "standard", "Standard"
        CDN_ONLY = "cdn_only", "CDN Only"
        DNS_ONLY = "dns_only", "DNS Only"

    dns_account = models.ForeignKey("DnsAccount", on_delete=models.CASCADE, related_name="zones")

    vendor_dns_zone = models.ManyToManyField(
        "registrar.VendorDnsZone", through="DnsZone_VendorDnsZone", related_name="zones"
    )  # type: ignore

    domain = models.OneToOneField("registrar.Domain", null=False, on_delete=models.CASCADE)  # apex domain

    soa = models.ForeignKey(
        "registrar.DnsSoa", on_delete=models.SET_DEFAULT, related_name="+", default=DnsSoa.get_default_pk
    )

    name = models.CharField(null=True, blank=True)

    nameservers = ArrayField(models.CharField(), null=True, blank=True)

    flatten_all_cnames = models.BooleanField(default=False)

    foundation_dns = models.BooleanField(default=False)

    multiprovider = models.BooleanField(default=False)

    ns_ttl = models.PositiveIntegerField(default=86400)

    secondary_overrides = models.BooleanField(default=False)

    zone_mode = models.CharField(choices=ZoneModes.choices, default="standard")

    def save(self, *args, **kwargs):
        """Save override for custom properties"""
        # Set default zone name to domain name
        if not self.name:
            self.name = self.domain.name
        # Set default SOA to default SOA settings
        if not self.soa:
            self.soa = DnsSoa
        super().save(*args, **kwargs)

    def get_active_x_zone_id(self):
        try:
            x_zone_id = self.zone_link.get(is_active=True).vendor_dns_zone.x_zone_id
        except ZonesLink.DoesNotExist:
            logger.debug(f"There is a database entry but no active vendor for this zone {self.name}")
            return None

        return x_zone_id
