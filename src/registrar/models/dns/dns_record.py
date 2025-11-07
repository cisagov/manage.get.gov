from django.db import models
from ..utility.time_stamped_model import TimeStampedModel
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
import re


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
            return ValidationError({"ttl": "TTL for unproxied records must be between 60 and 86400."})

        # Record name must either be '@' (root domain) or a subdomain of DNS zone domain
        return self.name == "@" or self.is_subdomain(self.name, self.zone.domain.name)

    def is_subdomain(self, name: str, root_domain: str):
        """Returns boolean if the domain name is found in the argument passed"""
        subdomain_pattern = r"([\w-]+\.)*"
        full_pattern = subdomain_pattern + root_domain
        regex = re.compile(full_pattern)
        return bool(regex.match(name))
