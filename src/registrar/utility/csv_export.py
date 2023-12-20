import csv
import logging
from datetime import datetime
from registrar.models.domain import Domain
from registrar.models.domain_information import DomainInformation
from registrar.models.public_contact import PublicContact
from django.db.models import Value
from django.db.models.functions import Coalesce
from itertools import chain
from django.utils import timezone

logger = logging.getLogger(__name__)

def export_domains_to_writer(writer, columns, sort_fields, filter_condition, filter_condition_for_additional_domains=None):
    # write columns headers to writer
    writer.writerow(columns)
    
    logger.info('export_domains_to_writer')
    logger.info(filter_condition)
    logger.info(filter_condition_for_additional_domains)

    # Get the domainInfos    
    domainInfos = DomainInformation.objects.filter(**filter_condition).order_by(*sort_fields)
    
    # Condition is true for export_data_growth_to_csv. This is an OR situation so we can' combine the filters
    # in one query.   
    if filter_condition_for_additional_domains is not None and 'domain__deleted_at__lt' in filter_condition_for_additional_domains:
        logger.info("Fetching deleted domains")
        deleted_domainInfos = DomainInformation.objects.filter(domain__state=Domain.State.DELETED).order_by("domain__deleted_at")        
        # Combine the two querysets into a single iterable
        all_domainInfos = list(chain(domainInfos, deleted_domainInfos))
    else:
        all_domainInfos = list(domainInfos)
        

    for domainInfo in all_domainInfos:
        security_contacts = domainInfo.domain.contacts.filter(contact_type=PublicContact.ContactTypeChoices.SECURITY)
        # For linter
        ao = " "
        if domainInfo.authorizing_official:
            first_name = domainInfo.authorizing_official.first_name or ""
            last_name = domainInfo.authorizing_official.last_name or ""
            ao = first_name + " " + last_name
        # create a dictionary of fields which can be included in output
        FIELDS = {
            "Domain name": domainInfo.domain.name,
            "Domain type": domainInfo.get_organization_type_display() + " - " + domainInfo.get_federal_type_display()
            if domainInfo.federal_type
            else domainInfo.get_organization_type_display(),
            "Agency": domainInfo.federal_agency,
            "Organization name": domainInfo.organization_name,
            "City": domainInfo.city,
            "State": domainInfo.state_territory,
            "AO": ao,
            "AO email": domainInfo.authorizing_official.email if domainInfo.authorizing_official else " ",
            "Security contact email": security_contacts[0].email if security_contacts else " ",
            "Status": domainInfo.domain.state,
            "Expiration date": domainInfo.domain.expiration_date,
            "Created at": domainInfo.domain.created_at,
            "Deleted at": domainInfo.domain.deleted_at,
        }
        writer.writerow([FIELDS.get(column, "") for column in columns])


def export_data_type_to_csv(csv_file):
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
    
def export_data_growth_to_csv(csv_file, start_date, end_date):
    
    if start_date:
        start_date_formatted = timezone.make_aware(datetime.strptime(start_date, "%Y-%m-%d"))
    else:
        # Handle the case where start_date is missing or empty
        # Default to a date that's prior to our first deployment
        logger.error(f"Error fetching the start date, will default to 12023/1/1")
        start_date_formatted = timezone.make_aware(datetime(2023, 11, 1))  # Replace with appropriate handling
        
    if end_date:
        end_date_formatted = timezone.make_aware(datetime.strptime(end_date, "%Y-%m-%d"))
    else:
        # Handle the case where end_date is missing or empty
        logger.error(f"Error fetching the end date, will default to now()")
        end_date_formatted = timezone.make_aware(datetime.now())  # Replace with appropriate handling
    
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
        "Deleted at",
        "Expiration date",
    ]
    sort_fields = [
        "created_at",
        "domain__name",
    ]
    filter_condition = {
        "domain__state__in": [
            Domain.State.READY,
        ],
        "domain__created_at__lt": end_date_formatted,
        "domain__created_at__gt": start_date_formatted,
    }
    filter_condition_for_additional_domains = {
        "domain__state__in": [
            Domain.State.DELETED,
        ],
        "domain__created_at__lt": end_date_formatted,
        "domain__created_at__gt": start_date_formatted,
    }
    export_domains_to_writer(writer, columns, sort_fields, filter_condition, filter_condition_for_additional_domains)
