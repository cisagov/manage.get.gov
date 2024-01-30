import csv
import logging
from datetime import datetime
from registrar.models.domain import Domain
from registrar.models.domain_information import DomainInformation
from registrar.models.public_contact import PublicContact
from django.db.models import Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from registrar.utility.enums import DefaultEmail

logger = logging.getLogger(__name__)


def write_header(writer, columns):
    """
    Receives params from the parent methods and outputs a CSV with a header row.
    Works with write_header as longas the same writer object is passed.
    """
    writer.writerow(columns)


def get_domain_infos(filter_condition, sort_fields):
    domain_infos = DomainInformation.objects.filter(**filter_condition).order_by(*sort_fields)
    return domain_infos


def write_row(writer, columns, domain_info):
    security_contacts = domain_info.domain.contacts.filter(contact_type=PublicContact.ContactTypeChoices.SECURITY)

    # For linter
    ao = " "
    if domain_info.authorizing_official:
        first_name = domain_info.authorizing_official.first_name or ""
        last_name = domain_info.authorizing_official.last_name or ""
        ao = first_name + " " + last_name

    security_email = " "
    if security_contacts:
        security_email = security_contacts[0].email

    invalid_emails = {DefaultEmail.LEGACY_DEFAULT, DefaultEmail.PUBLIC_CONTACT_DEFAULT}
    # These are default emails that should not be displayed in the csv report
    if security_email is not None and security_email.lower() in invalid_emails:
        security_email = "(blank)"

    # create a dictionary of fields which can be included in output
    FIELDS = {
        "Domain name": domain_info.domain.name,
        "Domain type": domain_info.get_organization_type_display() + " - " + domain_info.get_federal_type_display()
        if domain_info.federal_type
        else domain_info.get_organization_type_display(),
        "Agency": domain_info.federal_agency,
        "Organization name": domain_info.organization_name,
        "City": domain_info.city,
        "State": domain_info.state_territory,
        "AO": ao,
        "AO email": domain_info.authorizing_official.email if domain_info.authorizing_official else " ",
        "Security contact email": security_email,
        "Status": domain_info.domain.get_state_display(),
        "Expiration date": domain_info.domain.expiration_date,
        "Created at": domain_info.domain.created_at,
        "First ready": domain_info.domain.first_ready,
        "Deleted": domain_info.domain.deleted,
    }

    writer.writerow([FIELDS.get(column, "") for column in columns])


def write_body(
    writer,
    columns,
    sort_fields,
    filter_condition,
):
    """
    Receives params from the parent methods and outputs a CSV with fltered and sorted domains.
    Works with write_header as longas the same writer object is passed.
    """

    # Get the domainInfos
    domain_infos = get_domain_infos(filter_condition, sort_fields)

    all_domain_infos = list(domain_infos)

    # Write rows to CSV
    for domain_info in all_domain_infos:
        write_row(writer, columns, domain_info)


def export_data_type_to_csv(csv_file):
    """All domains report with extra columns"""

    writer = csv.writer(csv_file)
    # define columns to include in export
    columns = [
        "Domain name",
        "Domain type",
        "Agency",
        "Organization name",
        "City",
        "State",
        "AO",
        "AO email",
        "Security contact email",
        "Status",
        "Expiration date",
    ]
    # Coalesce is used to replace federal_type of None with ZZZZZ
    sort_fields = [
        "organization_type",
        Coalesce("federal_type", Value("ZZZZZ")),
        "federal_agency",
        "domain__name",
    ]
    filter_condition = {
        "domain__state__in": [
            Domain.State.READY,
            Domain.State.DNS_NEEDED,
            Domain.State.ON_HOLD,
        ],
    }
    write_header(writer, columns)
    write_body(writer, columns, sort_fields, filter_condition)


def export_data_full_to_csv(csv_file):
    """All domains report"""

    writer = csv.writer(csv_file)
    # define columns to include in export
    columns = [
        "Domain name",
        "Domain type",
        "Agency",
        "Organization name",
        "City",
        "State",
        "Security contact email",
    ]
    # Coalesce is used to replace federal_type of None with ZZZZZ
    sort_fields = [
        "organization_type",
        Coalesce("federal_type", Value("ZZZZZ")),
        "federal_agency",
        "domain__name",
    ]
    filter_condition = {
        "domain__state__in": [
            Domain.State.READY,
            Domain.State.DNS_NEEDED,
            Domain.State.ON_HOLD,
        ],
    }
    write_header(writer, columns)
    write_body(writer, columns, sort_fields, filter_condition)


def export_data_federal_to_csv(csv_file):
    """Federal domains report"""

    writer = csv.writer(csv_file)
    # define columns to include in export
    columns = [
        "Domain name",
        "Domain type",
        "Agency",
        "Organization name",
        "City",
        "State",
        "Security contact email",
    ]
    # Coalesce is used to replace federal_type of None with ZZZZZ
    sort_fields = [
        "organization_type",
        Coalesce("federal_type", Value("ZZZZZ")),
        "federal_agency",
        "domain__name",
    ]
    filter_condition = {
        "organization_type__icontains": "federal",
        "domain__state__in": [
            Domain.State.READY,
            Domain.State.DNS_NEEDED,
            Domain.State.ON_HOLD,
        ],
    }
    write_header(writer, columns)
    write_body(writer, columns, sort_fields, filter_condition)


def get_default_start_date():
    # Default to a date that's prior to our first deployment
    return timezone.make_aware(datetime(2023, 11, 1))


def get_default_end_date():
    # Default to now()
    return timezone.now()


def export_data_growth_to_csv(csv_file, start_date, end_date):
    """
    Growth report:
    Receive start and end dates from the view, parse them.
    Request from write_body READY domains that are created between
    the start and end dates, as well as DELETED domains that are deleted between
    the start and end dates. Specify sort params for both lists.
    """

    start_date_formatted = (
        timezone.make_aware(datetime.strptime(start_date, "%Y-%m-%d")) if start_date else get_default_start_date()
    )

    end_date_formatted = (
        timezone.make_aware(datetime.strptime(end_date, "%Y-%m-%d")) if end_date else get_default_end_date()
    )

    writer = csv.writer(csv_file)

    # define columns to include in export
    columns = [
        "Domain name",
        "Domain type",
        "Agency",
        "Organization name",
        "City",
        "State",
        "Status",
        "Expiration date",
        "Created at",
        "First ready",
        "Deleted",
    ]
    sort_fields = [
        "domain__first_ready",
        "domain__name",
    ]
    filter_condition = {
        "domain__state__in": [Domain.State.READY],
        "domain__first_ready__lte": end_date_formatted,
        "domain__first_ready__gte": start_date_formatted,
    }

    # We also want domains deleted between sar and end dates, sorted
    sort_fields_for_deleted_domains = [
        "domain__deleted",
        "domain__name",
    ]
    filter_condition_for_deleted_domains = {
        "domain__state__in": [Domain.State.DELETED],
        "domain__deleted__lte": end_date_formatted,
        "domain__deleted__gte": start_date_formatted,
    }

    write_header(writer, columns)
    write_body(writer, columns, sort_fields, filter_condition)
    write_body(writer, columns, sort_fields_for_deleted_domains, filter_condition_for_deleted_domains)
