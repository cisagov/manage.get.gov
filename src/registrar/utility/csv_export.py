import csv
import logging
from datetime import date, datetime
from registrar.models.domain import Domain
from registrar.models.domain_information import DomainInformation
from registrar.models.public_contact import PublicContact
from django.db.models import Value
from django.db.models.functions import Coalesce
from itertools import chain
from django.utils import timezone

logger = logging.getLogger(__name__)

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
        "Security contact email": security_contacts[0].email if security_contacts else " ",
        "Status": domain_info.domain.state,
        "Expiration date": domain_info.domain.expiration_date,
        "Created at": domain_info.domain.created_at,
        "Ready at": domain_info.domain.ready_at,
        "Deleted at": domain_info.domain.deleted_at,
    }
    writer.writerow([FIELDS.get(column, "") for column in columns])

def export_domains_to_writer(writer, columns, sort_fields, filter_condition, sort_fields_for_additional_domains=None, filter_condition_for_additional_domains=None):
    """
        Receives params from the parent methods and outputs a CSV with fltered and sorted domains.
        The 'additional' params enable us to concatenate 2 different filtered lists.
    """
    # write columns headers to writer
    writer.writerow(columns)

    # Get the domainInfos    
    domainInfos = get_domain_infos(filter_condition, sort_fields)
    
    # Condition is true for export_data_growth_to_csv. This is an OR situation so we can' combine the filters
    # in one query.   
    if filter_condition_for_additional_domains is not None and 'domain__deleted_at__lt' in filter_condition_for_additional_domains:
        # Get the deleted domain infos
        deleted_domainInfos = get_domain_infos(filter_condition_for_additional_domains, sort_fields_for_additional_domains)       
        # Combine the two querysets into a single iterable
        all_domainInfos = list(chain(domainInfos, deleted_domainInfos))
    else:
        all_domainInfos = list(domainInfos)
        
    # Write rows to CSV
    for domain_info in all_domainInfos:
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
    export_domains_to_writer(writer, columns, sort_fields, filter_condition)

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
    export_domains_to_writer(writer, columns, sort_fields, filter_condition)


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
    export_domains_to_writer(writer, columns, sort_fields, filter_condition)

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
    Request from export_domains_to_writer READY domains that are created between
    the start and end dates, as well as DELETED domains that are deleted between
    the start and end dates. Specify sort params for both lists.
    """
    
    start_date_formatted = (
        timezone.make_aware(datetime.strptime(start_date, "%Y-%m-%d"))
        if start_date
        else get_default_start_date()
    )

    end_date_formatted = (
        timezone.make_aware(datetime.strptime(end_date, "%Y-%m-%d"))
        if end_date
        else get_default_end_date()
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
        "Created at",
        "Ready at",
        "Deleted at",
        "Expiration date",
    ]
    sort_fields = [
        "created_at",
        "domain__name",
    ]
    filter_condition = {
        "domain__state__in": [Domain.State.READY],
        "domain__ready_at__lt": end_date_formatted,
        "domain__ready_at__gt": start_date_formatted,
    }
    
    # We also want domains deleted between sar and end dates, sorted
    sort_fields_for_additional_domains = [
        "domain__deleted_at",
        "domain__name",
    ]
    filter_condition_for_additional_domains = {
        "domain__state__in": [Domain.State.DELETED],
        "domain__created_at__lt": end_date_formatted,
        "domain__created_at__gt": start_date_formatted,
    }
    
    export_domains_to_writer(writer, columns, sort_fields, filter_condition, sort_fields_for_additional_domains, filter_condition_for_additional_domains)
