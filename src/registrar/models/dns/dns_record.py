import logging

from django.db import models, transaction
from ..utility.time_stamped_model import TimeStampedModel
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from registrar.validations import validate_dns_name
from registrar.utility.enums import DNSRecordTypes
from registrar.models.dns.dns_record_vendor_dns_record import DnsRecord_VendorDnsRecord as RecordsJoin
from registrar.models.dns.vendor_dns_record import VendorDnsRecord
from registrar.models.dns.vendor_dns_zone import VendorDnsZone
from registrar.models.dns.dns_zone import DnsZone
from registrar.models.domain import Domain

logger = logging.getLogger(__name__)


class DnsRecord(TimeStampedModel):

    dns_zone = models.ForeignKey("DnsZone", on_delete=models.CASCADE, related_name="records")

    vendor_dns_record = models.ManyToManyField(
        "registrar.VendorDnsRecord", through="DnsRecord_VendorDnsRecord", related_name="records"
    )  # type: ignore

    type = models.CharField(choices=DNSRecordTypes.choices)

    name = models.CharField(
        max_length=253,
        blank=False,
        null=False,
        validators=[validate_dns_name],
    )

    ttl = models.PositiveIntegerField(default=1)

    content = models.CharField(blank=True, null=True, max_length=2048)

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

        record_type = DNSRecordTypes(self.type)
        validator = record_type.validator

        if validator and self.content:
            try:
                validator(self.content)
            except ValidationError as e:
                errors["content"] = e.messages

        # Run validations involving multiple fields
        match record_type:
            case DNSRecordTypes.CNAME:
                if self._cname_record_name_matches_hostname(self.name, self.content):
                    raise ValidationError("CNAME record hostname must not match record name.")
            case _:
                return

        if errors:
            raise ValidationError(errors)

    def _cname_record_name_matches_hostname(self, record_name, hostname):
        """Validate that CNAME record name does not match hostname."""
        cf_record_name = record_name
        # TODO: Uncomment after later ticket to derive zone name from DNS record form (not model)
        # zone_name = self.dns_zone.name
        # if record_name == "@":
        #     cf_record_name = zone_name
        # if not record_name.endswith(zone_name):
        #     cf_record_name = f"{record_name}.{zone_name}"
        return cf_record_name == hostname

    def get_active_x_record_id(self) -> str | None:
        """Return the active external record id (x_record_id) for this DnsRecord via the join table."""
        try:
            link = (
                RecordsJoin.objects.filter(dns_record=self, is_active=True).select_related("vendor_dns_record").first()
            )
            if link and link.vendor_dns_record:
                return link.vendor_dns_record.x_record_id
        except Exception:
            logger.exception("Failed to resolve active vendor record id via RecordsJoin")
        return None

    @classmethod
    def get_for_domain(cls, domain: Domain, record_id: int) -> "DnsRecord | None":
        """Return the DnsRecord for a given id scoped to the domain's zone."""
        dns_zone = DnsZone.objects.filter(domain=domain).first()
        if not dns_zone:
            return None
        return cls.objects.filter(pk=record_id, dns_zone=dns_zone).first()

    @classmethod
    def get_ordered_for_zone(cls, dns_zone: "DnsZone"):
        """Return all records for a zone ordered by pk (matches counter assignment order)."""
        return cls.objects.filter(dns_zone=dns_zone).order_by("pk")

    @classmethod
    def zone_has_records(cls, domain: Domain) -> bool:
        """Return whether a domain's DNS zone has any existing records."""
        dns_zone = DnsZone.objects.filter(domain=domain).first()
        if not dns_zone:
            return False
        return cls.objects.filter(dns_zone=dns_zone).exists()

    @classmethod
    def get_by_x_record_id(cls, x_record_id: str) -> "DnsRecord | None":
        """Return the DnsRecord associated with the given x_record_id."""
        try:
            vendor_dns_record = VendorDnsRecord.objects.get(x_record_id=x_record_id)
            record_link = vendor_dns_record.record_link.filter(is_active=True).select_related("dns_record").first()
            if record_link and record_link.dns_record:
                return record_link.dns_record
        except Exception:
            logger.exception("Failed to resolve DnsRecord for vendor id %s", x_record_id)
        return None

    @classmethod
    def create_from_vendor_data(cls, x_zone_id: str, vendor_record_data: dict) -> None:
        """Create and save a DnsRecord and its join row from vendor API response data."""
        record_data = vendor_record_data["result"]
        x_record_id = record_data["id"]

        try:
            with transaction.atomic():
                vendor_dns_record = VendorDnsRecord.objects.create(
                    x_record_id=x_record_id,
                    x_created_at=record_data["created_on"],
                    x_updated_at=record_data["created_on"],
                )

                vendor_dns_zone = VendorDnsZone.objects.get(x_zone_id=x_zone_id)
                dns_zone = vendor_dns_zone.zone_link.get(is_active=True).dns_zone

                dns_record = cls.objects.create(
                    dns_zone=dns_zone,
                    type=record_data["type"],
                    name=record_data["name"],
                    ttl=record_data["ttl"],
                    content=record_data["content"],
                    comment=record_data["comment"],
                    tags=record_data["tags"],
                )

                RecordsJoin.objects.create(
                    dns_record=dns_record,
                    vendor_dns_record=vendor_dns_record,
                )

        except Exception as e:
            logger.error(f"Failed to create and save record to database: {str(e)}.")
            raise

    @classmethod
    def update_from_vendor_data(cls, x_zone_id: str, x_record_id: str, vendor_record_data: dict) -> None:
        """Update an existing DnsRecord from vendor API response data."""
        record_data = vendor_record_data["result"]
        excluded_fields = ["id", "type", "created_on"]

        try:
            with transaction.atomic():
                vendor_dns_record = VendorDnsRecord.objects.get(x_record_id=x_record_id)
                vendor_dns_zone = VendorDnsZone.objects.get(x_zone_id=x_zone_id)
                dns_zone = DnsZone.objects.get(vendor_dns_zone=vendor_dns_zone)
                dns_record = cls.objects.get(vendor_dns_record=vendor_dns_record, dns_zone=dns_zone)

                for record_field, record_value in record_data.items():
                    if record_field not in excluded_fields:
                        setattr(dns_record, record_field, record_value)
                dns_record.save()
        except Exception as e:
            logger.error(f"Failed to update and save record to database: {str(e)}.")
            raise
