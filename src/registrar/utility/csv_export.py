import csv
import logging
from datetime import datetime
from registrar.models.domain import Domain
from registrar.models.domain_invitation import DomainInvitation
from django.db.models import Case, When, Count, Value
from registrar.models.domain_request import DomainRequest
from registrar.models.domain_information import DomainInformation
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import F, Value, CharField
from django.db.models.functions import Concat, Coalesce

from registrar.models.public_contact import PublicContact
from registrar.models.user_domain_role import UserDomainRole
from registrar.utility.enums import DefaultEmail

logger = logging.getLogger(__name__)


def write_header(writer, columns):
    """
    Receives params from the parent methods and outputs a CSV with a header row.
    Works with write_header as long as the same writer object is passed.
    """
    writer.writerow(columns)


def get_domain_infos(filter_condition, sort_fields):
    """
    Returns DomainInformation objects filtered and sorted based on the provided conditions.
    filter_condition -> A dictionary of conditions to filter the objects.
    sort_fields -> A list of fields to sort the resulting query set.
    returns: A queryset of DomainInformation objects
    """
    domain_infos = (
        DomainInformation.objects.select_related("domain", "authorizing_official")
        .filter(**filter_condition)
        .order_by(*sort_fields)
        .distinct()
    )

    # Do a mass concat of the first and last name fields for authorizing_official.
    # The old operation was computationally heavy for some reason, so if we precompute
    # this here, it is vastly more efficient.
    domain_infos_cleaned = domain_infos.annotate(
        ao=Concat(
            Coalesce(F("authorizing_official__first_name"), Value("")),
            Value(" "),
            Coalesce(F("authorizing_official__last_name"), Value("")),
            output_field=CharField(),
        )
    )
    return domain_infos_cleaned


def parse_row_for_domain(
    columns,
    domain_info: DomainInformation,
    dict_security_emails=None,
    should_get_domain_managers=False,
    dict_domain_invitations_with_invited_status=None,
    dict_user_domain_roles=None,
):
    """Given a set of columns, generate a new row from cleaned column data"""

    # Domain should never be none when parsing this information
    if domain_info.domain is None:
        logger.error("Attemting to parse row for csv exports but Domain is none in a DomainInfo")
        raise ValueError("Domain is none")

    domain = domain_info.domain  # type: ignore

    # Grab the security email from a preset dictionary.
    # If nothing exists in the dictionary, grab from .contacts.
    if dict_security_emails is not None and domain.name in dict_security_emails:
        _email = dict_security_emails.get(domain.name)
        security_email = _email if _email is not None else " "
    else:
        # If the dictionary doesn't contain that data, lets filter for it manually.
        # This is a last resort as this is a more expensive operation.
        security_contacts = domain.contacts.filter(contact_type=PublicContact.ContactTypeChoices.SECURITY)
        _email = security_contacts[0].email if security_contacts else None
        security_email = _email if _email is not None else " "

    # These are default emails that should not be displayed in the csv report
    invalid_emails = {DefaultEmail.LEGACY_DEFAULT.value, DefaultEmail.PUBLIC_CONTACT_DEFAULT.value}
    if security_email.lower() in invalid_emails:
        security_email = "(blank)"

    if domain_info.federal_type and domain_info.organization_type == DomainRequest.OrgChoicesElectionOffice.FEDERAL:
        domain_type = f"{domain_info.get_organization_type_display()} - {domain_info.get_federal_type_display()}"
    else:
        domain_type = domain_info.get_organization_type_display()

    # create a dictionary of fields which can be included in output
    FIELDS = {
        "Domain name": domain.name,
        "Status": domain.get_state_display(),
        "Expiration date": domain.expiration_date,
        "Domain type": domain_type,
        "Agency": domain_info.federal_agency,
        "Organization name": domain_info.organization_name,
        "City": domain_info.city,
        "State": domain_info.state_territory,
        "AO": domain_info.ao,  # type: ignore
        "AO email": domain_info.authorizing_official.email if domain_info.authorizing_official else " ",
        "Security contact email": security_email,
        "Created at": domain.created_at,
        "First ready": domain.first_ready,
        "Deleted": domain.deleted,
    }

    if should_get_domain_managers:
        # Get lists of emails for active and invited domain managers

        dms_active_emails = dict_user_domain_roles.get(domain_info.domain.name, [])
        dms_invited_emails = dict_domain_invitations_with_invited_status.get(domain_info.domain.name, [])

        # Set up the "matching headers" + row field data for email and status
        i = 0  # Declare i outside of the loop to avoid a reference before assignment in the second loop
        for i, dm_email in enumerate(dms_active_emails, start=1):
            FIELDS[f"Domain manager {i}"] = dm_email
            FIELDS[f"DM{i} status"] = "R"

        # Continue enumeration from where we left off and add data for invited domain managers
        for j, dm_email in enumerate(dms_invited_emails, start=i + 1):
            FIELDS[f"Domain manager {j}"] = dm_email
            FIELDS[f"DM{j} status"] = "I"

    row = [FIELDS.get(column, "") for column in columns]
    return row


def _get_security_emails(sec_contact_ids):
    """
    Retrieve security contact emails for the given security contact IDs.
    """
    dict_security_emails = {}
    public_contacts = (
        PublicContact.objects.only("email", "domain__name")
        .select_related("domain")
        .filter(registry_id__in=sec_contact_ids)
    )

    # Populate a dictionary of domain names and their security contacts
    for contact in public_contacts:
        domain: Domain = contact.domain
        if domain is not None and domain.name not in dict_security_emails:
            dict_security_emails[domain.name] = contact.email
        else:
            logger.warning("csv_export -> Domain was none for PublicContact")

    return dict_security_emails


def count_domain_managers(domain_name, dict_domain_invitations_with_invited_status, dict_user_domain_roles):
    """Count active and invited domain managers"""
    dms_active = len(dict_user_domain_roles.get(domain_name, []))
    dms_invited = len(dict_domain_invitations_with_invited_status.get(domain_name, []))
    return dms_active, dms_invited


def update_columns(columns, dms_total, should_update_columns):
    """Update columns if necessary"""
    if should_update_columns:
        for i in range(1, dms_total + 1):
            email_column_header = f"Domain manager {i}"
            status_column_header = f"DM{i} status"
            if email_column_header not in columns:
                columns.append(email_column_header)
                columns.append(status_column_header)
        should_update_columns = False
    return columns, should_update_columns, dms_total


def update_columns_with_domain_managers(
    columns,
    domain_info,
    should_update_columns,
    dms_total,
    dict_domain_invitations_with_invited_status,
    dict_user_domain_roles,
):
    """Helper function to update columns with domain manager information"""

    domain_name = domain_info.domain.name

    try:
        dms_active, dms_invited = count_domain_managers(
            domain_name, dict_domain_invitations_with_invited_status, dict_user_domain_roles
        )

        if dms_active + dms_invited > dms_total:
            dms_total = dms_active + dms_invited
            should_update_columns = True

    except Exception as err:
        logger.error(f"Exception while parsing domain managers for reports: {err}")

    return update_columns(columns, dms_total, should_update_columns)


def build_dictionaries_for_domain_managers(dict_user_domain_roles, dict_domain_invitations_with_invited_status):
    """Helper function that builds dicts for invited users and active domain
    managers. We do so to avoid filtering within loops."""

    user_domain_roles = UserDomainRole.objects.all()

    # Iterate through each user domain role and populate the dictionary
    for user_domain_role in user_domain_roles:
        domain_name = user_domain_role.domain.name
        email = user_domain_role.user.email
        if domain_name not in dict_user_domain_roles:
            dict_user_domain_roles[domain_name] = []
        dict_user_domain_roles[domain_name].append(email)

    domain_invitations_with_invited_status = None
    domain_invitations_with_invited_status = DomainInvitation.objects.filter(
        status=DomainInvitation.DomainInvitationStatus.INVITED
    ).select_related("domain")

    # Iterate through each domain invitation and populate the dictionary
    for invite in domain_invitations_with_invited_status:
        domain_name = invite.domain.name
        email = invite.email
        if domain_name not in dict_domain_invitations_with_invited_status:
            dict_domain_invitations_with_invited_status[domain_name] = []
        dict_domain_invitations_with_invited_status[domain_name].append(email)

    return dict_user_domain_roles, dict_domain_invitations_with_invited_status


def write_csv_for_domains(
    writer,
    columns,
    sort_fields,
    filter_condition,
    should_get_domain_managers=False,
    should_write_header=True,
):
    """
    Receives params from the parent methods and outputs a CSV with filtered and sorted domains.
    Works with write_header as long as the same writer object is passed.
    should_get_domain_managers: Conditional bc we only use domain manager info for export_data_full_to_csv
    should_write_header: Conditional bc export_data_domain_growth_to_csv calls write_body twice
    """

    # Retrieve domain information and all sec emails
    all_domain_infos = get_domain_infos(filter_condition, sort_fields)
    sec_contact_ids = all_domain_infos.values_list("domain__security_contact_registry_id", flat=True)
    dict_security_emails = _get_security_emails(sec_contact_ids)
    paginator = Paginator(all_domain_infos, 1000)

    # Initialize variables
    dms_total = 0
    should_update_columns = False
    total_body_rows = []
    dict_user_domain_roles = {}
    dict_domain_invitations_with_invited_status = {}

    # Build dictionaries if necessary
    if should_get_domain_managers:
        dict_user_domain_roles, dict_domain_invitations_with_invited_status = build_dictionaries_for_domain_managers(
            dict_user_domain_roles, dict_domain_invitations_with_invited_status
        )

    # Process domain information
    for page_num in paginator.page_range:
        rows = []
        page = paginator.page(page_num)
        for domain_info in page.object_list:
            if should_get_domain_managers:
                columns, dms_total, should_update_columns = update_columns_with_domain_managers(
                    columns,
                    domain_info,
                    should_update_columns,
                    dms_total,
                    dict_domain_invitations_with_invited_status,
                    dict_user_domain_roles,
                )

            try:
                row = parse_row_for_domain(
                    columns,
                    domain_info,
                    dict_security_emails,
                    should_get_domain_managers,
                    dict_domain_invitations_with_invited_status,
                    dict_user_domain_roles,
                )
                rows.append(row)
            except ValueError:
                logger.error("csv_export -> Error when parsing row, domain was None")
                continue
        total_body_rows.extend(rows)

    if should_write_header:
        write_header(writer, columns)
    writer.writerows(total_body_rows)


def get_requests(filter_condition, sort_fields):
    """
    Returns DomainRequest objects filtered and sorted based on the provided conditions.
    filter_condition -> A dictionary of conditions to filter the objects.
    sort_fields -> A list of fields to sort the resulting query set.
    returns: A queryset of DomainRequest objects
    """
    requests = DomainRequest.objects.filter(**filter_condition).order_by(*sort_fields).distinct()
    return requests


def parse_row_for_requests(columns, request: DomainRequest):
    """Given a set of columns, generate a new row from cleaned column data"""

    requested_domain_name = "No requested domain"

    if request.requested_domain is not None:
        requested_domain_name = request.requested_domain.name

    if request.federal_type:
        request_type = f"{request.get_organization_type_display()} - {request.get_federal_type_display()}"
    else:
        request_type = request.get_organization_type_display()

    # create a dictionary of fields which can be included in output
    FIELDS = {
        "Requested domain": requested_domain_name,
        "Status": request.get_status_display(),
        "Organization type": request_type,
        "Agency": request.federal_agency,
        "Organization name": request.organization_name,
        "City": request.city,
        "State": request.state_territory,
        "AO email": request.authorizing_official.email if request.authorizing_official else " ",
        "Security contact email": request,
        "Created at": request.created_at,
        "Submission date": request.submission_date,
    }

    row = [FIELDS.get(column, "") for column in columns]
    return row


def write_csv_for_requests(
    writer,
    columns,
    sort_fields,
    filter_condition,
    should_write_header=True,
):
    """Receives params from the parent methods and outputs a CSV with filtered and sorted requests.
    Works with write_header as long as the same writer object is passed."""

    all_requests = get_requests(filter_condition, sort_fields)

    # Reduce the memory overhead when performing the write operation
    paginator = Paginator(all_requests, 1000)
    total_body_rows = []

    for page_num in paginator.page_range:
        page = paginator.page(page_num)
        rows = []
        for request in page.object_list:
            try:
                row = parse_row_for_requests(columns, request)
                rows.append(row)
            except ValueError:
                # This should not happen. If it does, just skip this row.
                # It indicates that DomainInformation.domain is None.
                logger.error("csv_export -> Error when parsing row, domain was None")
                continue
        total_body_rows.extend(rows)

    if should_write_header:
        write_header(writer, columns)
    writer.writerows(total_body_rows)


def export_data_type_to_csv(csv_file):
    """All domains report with extra columns"""

    writer = csv.writer(csv_file)
    # define columns to include in export
    columns = [
        "Domain name",
        "Status",
        "Expiration date",
        "Domain type",
        "Agency",
        "Organization name",
        "City",
        "State",
        "AO",
        "AO email",
        "Security contact email",
        # For domain manager we are pass it in as a parameter below in write_body
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
    write_csv_for_domains(
        writer, columns, sort_fields, filter_condition, should_get_domain_managers=True, should_write_header=True
    )


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
    write_csv_for_domains(
        writer, columns, sort_fields, filter_condition, should_get_domain_managers=False, should_write_header=True
    )


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
    write_csv_for_domains(
        writer, columns, sort_fields, filter_condition, should_get_domain_managers=False, should_write_header=True
    )


def get_default_start_date():
    # Default to a date that's prior to our first deployment
    return timezone.make_aware(datetime(2023, 11, 1))


def get_default_end_date():
    # Default to now()
    return timezone.now()


def format_start_date(start_date):
    return timezone.make_aware(datetime.strptime(start_date, "%Y-%m-%d")) if start_date else get_default_start_date()


def format_end_date(end_date):
    return timezone.make_aware(datetime.strptime(end_date, "%Y-%m-%d")) if end_date else get_default_end_date()


def export_data_domain_growth_to_csv(csv_file, start_date, end_date):
    """
    Growth report:
    Receive start and end dates from the view, parse them.
    Request from write_body READY domains that are created between
    the start and end dates, as well as DELETED domains that are deleted between
    the start and end dates. Specify sort params for both lists.
    """

    start_date_formatted = format_start_date(start_date)
    end_date_formatted = format_end_date(end_date)
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

    write_csv_for_domains(
        writer, columns, sort_fields, filter_condition, should_get_domain_managers=False, should_write_header=True
    )
    write_csv_for_domains(
        writer,
        columns,
        sort_fields_for_deleted_domains,
        filter_condition_for_deleted_domains,
        should_get_domain_managers=False,
        should_write_header=False,
    )


def get_sliced_domains(filter_condition):
    """Get filtered domains counts sliced by org type and election office.
    Pass distinct=True when filtering by permissions so we do not to count multiples
    when a domain has more that one manager.
    """
    return get_org_type_counts(DomainInformation, filter_condition)

def get_sliced_requests(filter_condition):
    """Get filtered requests counts sliced by org type and election office."""
    return get_org_type_counts(DomainRequest, filter_condition)

def get_org_type_counts(model_class, filter_condition):
    """Returns a list of counts for each org type"""
    
    # Count all org types, such as federal
    dynamic_count_dict = {}
    for choice in DomainRequest.OrganizationChoices:
        choice_name = f"{choice}_count"
        dynamic_count_dict[choice_name] = _org_type_count_query_builder(choice)
    
    # Static counts
    static_count_dict = {
        # Count all distinct records
        "total_count": Count('id'),
        # Count all election boards
        "election_board_count": Count(Case(When(is_election_board=True, then=1))),
    }

    # Merge static counts with dynamic organization type counts
    merged_count_dict = {**static_count_dict, **dynamic_count_dict}

    # Perform a single query with conditional aggregation
    model_queryset = model_class.objects.filter(**filter_condition).distinct()
    aggregates = model_queryset.aggregate(**merged_count_dict)

    # This can be automated but for the sake of readability, this is fixed for now.
    # To automate this would also mean the added benefit of 
    # auto-updating (automatically adds new org types) charts,
    # but that requires an upstream refactor.
    return [
        # Total number of records
        aggregates['total_count'],
        # Number of records with org type FEDERAL
        aggregates['federal_count'],
        # Number of records with org type INTERSTATE
        aggregates['interstate_count'],
        # Number of records with org type STATE_OR_TERRITORY
        aggregates['state_or_territory_count'],
        # Number of records for TRIBAL
        aggregates['tribal_count'],
        # Number of records for COUNTY
        aggregates['county_count'],
        # Number of records for CITY
        aggregates['city_count'],
        # Number of records for SPECIAL_DISTRICT
        aggregates['special_district_count'],
        # Number of records for SCHOOL_DISTRICT
        aggregates['school_district_count'],
        # Number of records for ELECTION_BOARD
        aggregates['election_board_count'],
    ]

def _org_type_count_query_builder(generic_org_type):
    """
    Returns an expression that counts the number of a given generic_org_type.
    On the backend (the DB), this returns an array of "1" which is then counted by the expression.
    Used within an .aggregate call, but this essentially performs the same as queryset.count()

    We use this as opposed to queryset.count() because when this operation is repeated multiple times,
    it is more efficient to do these once in the DB rather than multiple times (as each count consitutes a call)
    """
    return Count(Case(When(generic_org_type=generic_org_type, then=1)))

def export_data_managed_domains_to_csv(csv_file, start_date, end_date):
    """Get counts for domains that have domain managers for two different dates,
    get list of managed domains at end_date."""

    start_date_formatted = format_start_date(start_date)
    end_date_formatted = format_end_date(end_date)
    writer = csv.writer(csv_file)
    columns = [
        "Domain name",
        "Domain type",
    ]
    sort_fields = [
        "domain__name",
    ]
    filter_managed_domains_start_date = {
        "domain__permissions__isnull": False,
        "domain__first_ready__lte": start_date_formatted,
    }
    managed_domains_sliced_at_start_date = get_sliced_domains(filter_managed_domains_start_date)

    writer.writerow(["MANAGED DOMAINS COUNTS AT START DATE"])
    writer.writerow(
        [
            "Total",
            "Federal",
            "Interstate",
            "State or territory",
            "Tribal",
            "County",
            "City",
            "Special district",
            "School district",
            "Election office",
        ]
    )
    writer.writerow(managed_domains_sliced_at_start_date)
    writer.writerow([])

    filter_managed_domains_end_date = {
        "domain__permissions__isnull": False,
        "domain__first_ready__lte": end_date_formatted,
    }
    managed_domains_sliced_at_end_date = get_sliced_domains(filter_managed_domains_end_date)

    writer.writerow(["MANAGED DOMAINS COUNTS AT END DATE"])
    writer.writerow(
        [
            "Total",
            "Federal",
            "Interstate",
            "State or territory",
            "Tribal",
            "County",
            "City",
            "Special district",
            "School district",
            "Election office",
        ]
    )
    writer.writerow(managed_domains_sliced_at_end_date)
    writer.writerow([])

    write_csv_for_domains(
        writer,
        columns,
        sort_fields,
        filter_managed_domains_end_date,
        should_get_domain_managers=True,
        should_write_header=True,
    )


def export_data_unmanaged_domains_to_csv(csv_file, start_date, end_date):
    """Get counts for domains that do not have domain managers for two different dates,
    get list of unmanaged domains at end_date."""

    start_date_formatted = format_start_date(start_date)
    end_date_formatted = format_end_date(end_date)
    writer = csv.writer(csv_file)
    columns = [
        "Domain name",
        "Domain type",
    ]
    sort_fields = [
        "domain__name",
    ]

    filter_unmanaged_domains_start_date = {
        "domain__permissions__isnull": True,
        "domain__first_ready__lte": start_date_formatted,
    }
    unmanaged_domains_sliced_at_start_date = get_sliced_domains(filter_unmanaged_domains_start_date)

    writer.writerow(["UNMANAGED DOMAINS AT START DATE"])
    writer.writerow(
        [
            "Total",
            "Federal",
            "Interstate",
            "State or territory",
            "Tribal",
            "County",
            "City",
            "Special district",
            "School district",
            "Election office",
        ]
    )
    writer.writerow(unmanaged_domains_sliced_at_start_date)
    writer.writerow([])

    filter_unmanaged_domains_end_date = {
        "domain__permissions__isnull": True,
        "domain__first_ready__lte": end_date_formatted,
    }
    unmanaged_domains_sliced_at_end_date = get_sliced_domains(filter_unmanaged_domains_end_date)

    writer.writerow(["UNMANAGED DOMAINS AT END DATE"])
    writer.writerow(
        [
            "Total",
            "Federal",
            "Interstate",
            "State or territory",
            "Tribal",
            "County",
            "City",
            "Special district",
            "School district",
            "Election office",
        ]
    )
    writer.writerow(unmanaged_domains_sliced_at_end_date)
    writer.writerow([])

    write_csv_for_domains(
        writer,
        columns,
        sort_fields,
        filter_unmanaged_domains_end_date,
        should_get_domain_managers=False,
        should_write_header=True,
    )


def export_data_requests_growth_to_csv(csv_file, start_date, end_date):
    """
    Growth report:
    Receive start and end dates from the view, parse them.
    Request from write_requests_body SUBMITTED requests that are created between
    the start and end dates. Specify sort params.
    """

    start_date_formatted = format_start_date(start_date)
    end_date_formatted = format_end_date(end_date)
    writer = csv.writer(csv_file)
    # define columns to include in export
    columns = [
        "Requested domain",
        "Organization type",
        "Submission date",
    ]
    sort_fields = [
        "requested_domain__name",
    ]
    filter_condition = {
        "status": DomainRequest.DomainRequestStatus.SUBMITTED,
        "submission_date__lte": end_date_formatted,
        "submission_date__gte": start_date_formatted,
    }

    write_csv_for_requests(writer, columns, sort_fields, filter_condition, should_write_header=True)
