import csv
from registrar.models.domain import Domain
from registrar.models.domain_information import DomainInformation
from registrar.models.public_contact import PublicContact

def export_data_type_to_csv(csv_file):
    writer = csv.writer(csv_file)
    # Write your data to the CSV here
    writer.writerow(
        [
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
    )  # Include the appropriate headers
    # Loop through and write your data rows
    for domain in Domain.objects.all().order_by('name'):
        domain_information, _ = DomainInformation.objects.get_or_create(domain=domain)
        security_contacts = domain.contacts.filter(contact_type=PublicContact.ContactTypeChoices.SECURITY)

        writer.writerow(
            [
                domain.name,
                domain_information.federal_type,
                domain_information.federal_agency,
                domain_information.organization_name,
                domain_information.city,
                domain_information.state_territory,
                domain_information.authorizing_official.first_name + " " + domain_information.authorizing_official.last_name,
                domain_information.authorizing_official.email,
                domain_information.submitter.first_name + " " + domain_information.submitter.last_name,
                domain_information.submitter.title,
                domain_information.submitter.email,
                domain_information.submitter.phone,
                security_contacts[0].email if security_contacts.exists() else " ",
                # domain.contacts.all().filter(contact_type=PublicContact.ContactTypeChoices.SECURITY)[0].email if len(domain.contacts.all().filter(contact_type=PublicContact.ContactTypeChoices.SECURITY)) else " ",
                domain.state,
                # domain.expiration_date,
            ]
        )  # Include the appropriate fields

def export_data_full_to_csv(csv_file):
    writer = csv.writer(csv_file)
    # Write your data to the CSV here
    writer.writerow(['Name', 'State', ...])  # Include the appropriate headers
    # Loop through and write your data rows
    for data_row in Domain.objects.all():
        writer.writerow([data_row.name, data_row.state, ...])  # Include the appropriate fields

def export_data_federal_to_csv(csv_file):
    writer = csv.writer(csv_file)
    # Write your data to the CSV here
    writer.writerow(['Name', 'State', ...])  # Include the appropriate headers
    # Loop through and write your data rows
    for data_row in Domain.objects.all():
        writer.writerow([data_row.name, data_row.state, ...])  # Include the appropriate fields