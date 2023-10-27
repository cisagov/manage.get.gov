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
            "Domain type": domainInfo.organization_type,
            "Federal agency": domainInfo.federal_agency,
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
        }
        writer.writerow([FIELDS.get(column, "") for column in columns])


def export_data_type_to_csv(csv_file):
    writer = csv.writer(csv_file)
    # define columns to include in export
    columns = [
        "Domain name",
        "Domain type",
        "Federal agency",
        "Organization name",
        "City",
        "State",
        "AO",
        "AO email",
        "Security Contact Email",
        "Status",
        # 'Expiration Date'
    ]
    sort_fields = ["domain__name"]
    filter_condition = {
        "domain__state": Domain.State.READY,
        "domain__state": Domain.State.DNS_NEEDED,
        "domain__state": Domain.State.ON_HOLD,
    }
    export_domains_to_writer(writer, columns, sort_fields, filter_condition)


def export_data_full_to_csv(csv_file):
    writer = csv.writer(csv_file)
    # define columns to include in export
    columns = [
        "Domain name",
        "Domain type",
        "Federal agency",
        "Organization name",
        "City",
        "State",
        "Security Contact Email",
    ]
    sort_fields = ["domain__name", "federal_agency", "organization_type"]
    filter_condition = {
        "domain__state": Domain.State.READY,
        "domain__state": Domain.State.DNS_NEEDED,
        "domain__state": Domain.State.ON_HOLD,
    }
    export_domains_to_writer(writer, columns, sort_fields, filter_condition)


def export_data_federal_to_csv(csv_file):
    writer = csv.writer(csv_file)
    # define columns to include in export
    columns = [
        "Domain name",
        "Domain type",
        "Federal agency",
        "Organization name",
        "City",
        "State",
        "Security Contact Email",
    ]
    sort_fields = ["domain__name", "federal_agency", "organization_type"]
    filter_condition = {
        "organization_type__icontains": "federal",
        "domain__state": Domain.State.READY,
        "domain__state": Domain.State.DNS_NEEDED,
        "domain__state": Domain.State.ON_HOLD,
    }
    export_domains_to_writer(writer, columns, sort_fields, filter_condition)
