import csv
from datetime import datetime
from registrar.models.domain import Domain
from registrar.models.domain_information import DomainInformation
from registrar.models.public_contact import PublicContact
from django.db.models import Value
from django.db.models.functions import Coalesce
from itertools import chain


def export_domains_to_writer(writer, columns, sort_fields, filter_condition):
    # write columns headers to writer
    writer.writerow(columns)

    
    print(f"filter_condition {filter_condition}")
    domainInfos = DomainInformation.objects.filter(**filter_condition).order_by(*sort_fields)
    
    if 'domain__created_at__gt' in filter_condition:
        
        deleted_domainInfos = DomainInformation.objects.filter(domain__state=Domain.State.DELETED).order_by("domain__deleted_at")
        print(f"filtering by deleted {domainInfos}")
        
        # Combine the two querysets into a single iterable
        all_domainInfos = list(chain(domainInfos, deleted_domainInfos))
    else:
        all_domainInfos = list(domainInfos)
        

    for domainInfo in all_domainInfos:
        security_contacts = domainInfo.domain.contacts.filter(contact_type=PublicContact.ContactTypeChoices.SECURITY)
        print(f"regular filtering {domainInfos}")
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
    
    print(f'start_date {start_date}')
    print(f'end_date {end_date}')
    
    # Check if start_date is not empty before using strptime
    if start_date:
        start_date_formatted = datetime.strptime(start_date, "%Y-%m-%d")
        print(f'start_date_formatted {start_date_formatted}')
    else:
        # Handle the case where start_date is missing or empty
        print('ON NO')
        # TODO: use Nov 1 2023
        start_date_formatted = None  # Replace with appropriate handling
        
    if end_date:
        end_date_formatted = datetime.strptime(end_date, "%Y-%m-%d")
        print(f'end_date_formatted {end_date_formatted}')
    else:
        # Handle the case where start_date is missing or empty
        print('ON NO')
        # TODO: use now
        end_date_formatted = None  # Replace with appropriate handling
    
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
            Domain.State.UNKNOWN,
            Domain.State.DELETED,
        ],
        "domain__created_at__lt": end_date_formatted,
        "domain__created_at__gt": start_date_formatted,
    }
    export_domains_to_writer(writer, columns, sort_fields, filter_condition)
