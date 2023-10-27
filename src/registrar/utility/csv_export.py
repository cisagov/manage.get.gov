import csv
from registrar.models.domain import Domain
from registrar.models.domain_information import DomainInformation
from registrar.models.public_contact import PublicContact

# TODO pass sort order and filter as arguments rather than domains
def export_domains_to_writer(writer, domains, columns):
    # write columns headers to writer
    writer.writerow(columns)

    for domain in Domain.objects.all().order_by('name'):
        domain_information, _ = DomainInformation.objects.get_or_create(domain=domain)
        security_contacts = domain.contacts.filter(contact_type=PublicContact.ContactTypeChoices.SECURITY)

        # create a dictionary of fields to include
        FIELDS = {
            'Domain name': domain.name,
            'Domain type': domain_information.federal_type,
            'Federal agency': domain_information.federal_agency,
            'Organization name': domain_information.organization_name,
            'City': domain_information.city,
            'State': domain_information.state_territory,
            'AO': domain_information.authorizing_official.first_name + " " + domain_information.authorizing_official.last_name,
            'AO email': domain_information.authorizing_official.email,
            'Submitter': domain_information.submitter.first_name + " " + domain_information.submitter.last_name,
            'Submitter title': domain_information.submitter.title,
            'Submitter email': domain_information.submitter.email,
            'Submitter phone': domain_information.submitter.phone,
            'Security Contact Email': security_contacts[0].email if security_contacts.exists() else " ",
            'Status': domain.state,
        }
        writer.writerow(
            [FIELDS.get(column,'') for column in columns]
        )

def export_data_type_to_csv(csv_file):
    writer = csv.writer(csv_file)
    # define columns to include in export
    columns = [
        'Domain name',
        'Domain type',
        'Federal agency',
        'Organization name',
        'City',
        'State',
        'AO',
        'AO email',
        'Submitter',
        'Submitter title',
        'Submitter email',
        'Submitter phone',
        'Security Contact Email',
        'Status',
        # 'Expiration Date'
    ]
    # define domains to be exported
    domains = Domain.objects.all().order_by('name')
    export_domains_to_writer(writer, domains, columns)

def export_data_full_to_csv(csv_file):
    writer = csv.writer(csv_file)
    # define columns to include in export
    columns = [
        'Domain name',
        'Domain type',
        'Federal agency',
        'Organization name',
        'City',
        'State',
        'Security Contact Email',
    ]
    # define domains to be exported
    # TODO order by fields in domain information
    domains = Domain.objects.all().order_by('name')
    export_domains_to_writer(writer, domains, columns)

def export_data_federal_to_csv(csv_file):
    writer = csv.writer(csv_file)
    # define columns to include in export
    columns = [
        'Domain name',
        'Domain type',
        'Federal agency',
        'Organization name',
        'City',
        'State',
        'Security Contact Email',
    ]
    # define domains to be exported
    # TODO order by fields in domain information
    # TODO filter by domain type
    domains = Domain.objects.all().order_by('name')
    export_domains_to_writer(writer, domains, columns)