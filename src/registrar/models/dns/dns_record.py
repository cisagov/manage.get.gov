import logging

from django.db import models, transaction
from django.db.models import Q
from django.core.validators import MinValueValidator, MaxValueValidator
from ..utility.time_stamped_model import TimeStampedModel
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from registrar.validations import (
    DNS_NAME_LENGTH_ERROR_MESSAGE,
    DNS_RECORD_PRIORITY_REQUIRED_ERROR_MESSAGE,
    validate_dns_name,
)
from registrar.utility.enums import DNSRecordTypes, format_dns_ttl
from registrar.models.dns.dns_record_vendor_dns_record import DnsRecord_VendorDnsRecord as RecordsJoin
from registrar.models.dns.vendor_dns_record import VendorDnsRecord
from registrar.models.dns.vendor_dns_zone import VendorDnsZone
from registrar.models.dns.dns_zone import DnsZone
from registrar.models.domain import Domain

logger = logging.getLogger(__name__)


class DnsRecord(TimeStampedModel):
    """DNS record model with RFC 1034 compliance for record type constraints."""

    # CNAME records cannot coexist with other record types.
    # DNS also prevents multiple CNAME records at the same name (only one CNAME per label).
    CONFLICTING_RECORD_TYPES = {
        DNSRecordTypes.CNAME: [DNSRecordTypes.A, DNSRecordTypes.AAAA, DNSRecordTypes.CNAME],
        DNSRecordTypes.A: [DNSRecordTypes.CNAME],
        DNSRecordTypes.AAAA: [DNSRecordTypes.CNAME],
    }

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
        error_messages={"max_length": DNS_NAME_LENGTH_ERROR_MESSAGE},
    )

    ttl = models.PositiveIntegerField(default=1)

    content = models.CharField(blank=True, null=True, max_length=2048)

    priority = models.PositiveIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(65535)],
    )

    comment = models.CharField(blank=True, null=True, max_length=500)

    tags = ArrayField(models.CharField(), null=True, blank=True, default=list)

    @property
    def ttl_display(self) -> str:
        return format_dns_ttl(self.ttl)

    def _validate_ttl(self, errors):
        """Validate TTL is within allowed range."""
        # TTL must be between 60 and 86400.
        # If we add proxy field to records in the future, we can also allow TTL=1 as below:
        # if self.ttl == 1: return self.proxy
        if self.ttl < 60 or self.ttl > 86400:
            errors["ttl"] = ["TTL for unproxied records must be between 60 and 86400."]

    def _validate_content(self, record_type, errors):
        """Validate content based on record type."""
        validator = record_type.validator
        if validator and self.content:
            try:
                validator(self.content)
            except ValidationError as e:
                errors["content"] = e.messages

    def _validate_mx_priority(self, record_type, errors):
        """Validate MX record has priority."""
        if record_type == DNSRecordTypes.MX and self.priority is None:
            errors["priority"] = [DNS_RECORD_PRIORITY_REQUIRED_ERROR_MESSAGE]

    def _validate_exclusive_names(self, record_type, errors):
        """Validate CNAME/A/AAAA records don't share names.

        Uses _name_q to handle label/FQDN and @/domain-name equivalences so that
        records stored in different but equivalent forms are still detected.
        """
        if not (self.name and self.dns_zone_id):
            return

        if record_type not in self.CONFLICTING_RECORD_TYPES:
            return

        # Resolve domain name for matching (e.g. "@" vs "example.gov",
        # "sub" vs "sub.example.gov").
        try:
            domain_name = DnsZone.objects.get(pk=self.dns_zone_id).domain.name
        except DnsZone.DoesNotExist:
            domain_name = None

        conflict = DnsRecord.objects.filter(
            dns_zone_id=self.dns_zone_id,
            type__in=self.CONFLICTING_RECORD_TYPES[record_type],
        ).filter(self._name_q(self.name, domain_name))

        if self.pk:
            conflict = conflict.exclude(pk=self.pk)

        if conflict.exists():
            errors["name"] = ["A record with that name already exists. Names must be unique."]

    def _normalize_name(self) -> None:
        """Lowercase the record name so storage matches DNS case-insensitivity."""
        if self.name:
            self.name = self.name.lower()

    def full_clean(self, *args, **kwargs):
        # Normalize before field validators and clean() run so self.name is
        # consistently lowercased for every downstream check, not just at save-time.
        self._normalize_name()
        super().full_clean(*args, **kwargs)

    def save(self, *args, **kwargs):
        # Safety net for paths that bypass full_clean (e.g., create_from_vendor_data).
        self._normalize_name()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        self._normalize_name()
        errors = {}

        self._validate_ttl(errors)
        record_type = DNSRecordTypes(self.type)
        self._validate_content(record_type, errors)
        self._validate_mx_priority(record_type, errors)
        self._validate_exclusive_names(record_type, errors)

        if errors:
            raise ValidationError(errors)

    @classmethod
    def _equivalent_name_forms(cls, name: str, domain_name: str | None) -> list[str]:
        """Return every stored-form of a DNS name within a zone.

        DNS names have two equivalences that dup/conflict checks must span, because
        records may be stored either way depending on source (user input vs vendor sync):
          - Root of the zone: "@" ≡ the bare domain name ("example.gov").
          - Label/FQDN: "www" ≡ "www.example.gov".
        Case is handled by iexact in the filter, not here.
        """
        forms = {name}
        if not domain_name:
            return list(forms)

        name_lower = name.lower()
        domain_lower = domain_name.lower()

        if name_lower == "@":
            forms.add(domain_name)
        elif name_lower == domain_lower:
            forms.add("@")

        if name_lower != "@" and name_lower != domain_lower and not name_lower.endswith(f".{domain_lower}"):
            forms.add(f"{name}.{domain_name}")

        if name_lower != domain_lower and name_lower.endswith(f".{domain_lower}"):
            label = name[: -(len(domain_name) + 1)]
            if label:
                forms.add(label)

        return list(forms)

    @classmethod
    def _name_q(cls, name: str, domain_name: str | None) -> Q:
        """Case-insensitive name filter that matches every equivalent stored-form.

        Covers label↔FQDN and root↔bare-domain equivalences — see _equivalent_name_forms.
        """
        q = Q()
        for form in cls._equivalent_name_forms(name, domain_name):
            q |= Q(name__iexact=form)
        return q

    @classmethod
    def has_duplicate_record(
        cls,
        domain_name: str,
        record_type: str,
        name: str,
        content: str,
        priority: int | None = None,
        exclude_record_id: int | None = None,
    ) -> bool:
        """Return True if a record with identical data already exists in the zone.

        A record is a duplicate when type, name, and content all match (plus priority
        for MX). TTL is not part of identity — two records that differ only in TTL are
        still duplicates. The zone is resolved from domain_name internally so callers
        don't need to query DnsZone first.

        Args:
            domain_name: The domain whose zone should be searched. Returns False if the
                domain has no DNS zone.
            record_type: The record type being added (e.g., DNSRecordTypes.A).
            name: The record name (can be label or FQDN; DNS is case-insensitive).
            content: The record content to match against (case-insensitive).
            priority: The MX priority. Only compared when record_type is MX;
                ignored otherwise.
            exclude_record_id: Record ID to exclude (for editing existing records).

        Returns:
            True if a duplicate exists, False otherwise.
        """
        if not (name and content and domain_name):
            return False

        dns_zone_id = DnsZone.get_zone_id_for_domain(domain_name)
        if not dns_zone_id:
            return False

        query = cls.objects.filter(
            dns_zone_id=dns_zone_id,
            type=record_type,
            content__iexact=content,
        ).filter(cls._name_q(name, domain_name))

        if DNSRecordTypes(record_type) == DNSRecordTypes.MX:
            query = query.filter(priority=priority)

        if exclude_record_id:
            query = query.exclude(pk=exclude_record_id)

        return query.exists()

    @classmethod
    def has_name_conflict(
        cls,
        domain_name: str,
        record_type: str,
        name: str,
        exclude_record_id: int | None = None,
    ) -> bool:
        """Return True if the record's name collides with an incompatible type in the zone.

        Per RFC 1034 Section 3.6.2, only CNAME/A/AAAA records have name conflicts.
        Handles both label and FQDN input formats with case-insensitive matching.
        The zone is resolved from domain_name internally so callers don't need to
        query DnsZone first.

        Args:
            domain_name: The domain whose zone should be searched. Returns False if the
                domain has no DNS zone.
            record_type: The record type being added (e.g., DNSRecordTypes.CNAME).
            name: The record name (can be label or FQDN; DNS is case-insensitive).
            exclude_record_id: Record ID to exclude (for editing existing records).

        Returns:
            True if a conflict exists, False otherwise.
        """
        record_type_enum = DNSRecordTypes(record_type)
        if record_type_enum not in cls.CONFLICTING_RECORD_TYPES or not (name and domain_name):
            return False

        dns_zone_id = DnsZone.get_zone_id_for_domain(domain_name)
        if not dns_zone_id:
            return False

        query = cls.objects.filter(
            dns_zone_id=dns_zone_id,
            type__in=cls.CONFLICTING_RECORD_TYPES[record_type_enum],
        ).filter(cls._name_q(name, domain_name))

        if exclude_record_id:
            query = query.exclude(pk=exclude_record_id)

        return query.exists()

    @classmethod
    def _validate_cname_record_name_dne_hostname(self, record_name, hostname, domain_name=None):
        """Validate that CNAME record name does not match hostname."""
        cf_record_name = record_name
        if domain_name:
            if record_name == "@":
                cf_record_name = domain_name
            elif not record_name.endswith(domain_name):
                cf_record_name = f"{record_name}.{domain_name}"
        if cf_record_name == hostname:
            raise ValidationError("CNAME record hostname must not match record name.")

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
        # Real Cloudflare lowercases names on save; mirror that here so all call sites
        # (including any that read the vendor payload directly) see a consistent value.
        if record_data.get("name"):
            record_data["name"] = record_data["name"].lower()

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
                    priority=record_data.get("priority"),
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
        # Real Cloudflare lowercases names on save; mirror that here so all call sites
        # (including any that read the vendor payload directly) see a consistent value.
        if record_data.get("name"):
            record_data["name"] = record_data["name"].lower()

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
