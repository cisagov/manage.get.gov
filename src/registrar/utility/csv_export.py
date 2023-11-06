import csv
from registrar.models.domain import Domain
from registrar.models.domain_information import DomainInformation
from registrar.models.public_contact import PublicContact


def export_domains_to_writer(writer, columns, sort_fields, filter_condition):
    # write columns headers to writer
    writer.writerow(columns)

    domainInfos = DomainInformation.objects.filter(**filter_condition).order_by(
        *sort_fields
    )
    for domainInfo in domainInfos:
        security_contacts = domainInfo.domain.contacts.filter(
            contact_type=PublicContact.ContactTypeChoices.SECURITY
        )

        # create a dictionary of fields which can be included in output
        FIELDS = {
            "Domain name": domainInfo.domain.name,
            "Domain type": domainInfo.get_organization_type_display()
            + " - "
            + domainInfo.get_federal_type_display()
            if domainInfo.federal_type
            else domainInfo.get_organization_type_display(),
            "Agency": domainInfo.federal_agency,
            "Organization name": domainInfo.organization_name,
            "City": domainInfo.city,
            "State": domainInfo.state_territory,
            "AO": domainInfo.authorizing_official.first_name
            + " "
            + domainInfo.authorizing_official.last_name
            if domainInfo.authorizing_official
            else " ",
            "AO email": domainInfo.authorizing_official.email
            if domainInfo.authorizing_official
            else " ",
            "Security Contact Email": security_contacts[0].email
            if security_contacts
            else " ",
            "Status": domainInfo.domain.state,
            "Expiration Date": domainInfo.domain.expiration_date,
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
        "Security Contact Email",
        "Status",
        "Expiration Date",
    ]
    sort_fields = ["organization_type", "federal_agency", "domain__name"]
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
        "Security Contact Email",
    ]
    sort_fields = ["organization_type", "federal_agency", "domain__name"]
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
        "Security Contact Email",
    ]
    sort_fields = ["organization_type", "federal_agency", "domain__name"]
    filter_condition = {
        "organization_type__icontains": "federal",
        "domain__state__in": [
            Domain.State.READY,
            Domain.State.DNS_NEEDED,
            Domain.State.ON_HOLD,
        ],
    }
    export_domains_to_writer(writer, columns, sort_fields, filter_condition)
