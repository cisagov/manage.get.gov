import csv
import logging
from datetime import datetime
from registrar.models import Domain, DomainInvitation, DomainRequest, DomainInformation, User, PublicContact, UserDomainRole
from django.db.models import QuerySet, Value, Case, When, CharField, Count, Q, F, Value, CharField
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models.functions import Concat, Coalesce
from django.contrib.postgres.aggregates import StringAgg
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
        "First ready on": domain.first_ready or "(blank)",
        "Expiration date": domain.expiration_date or "(blank)",
        "Domain type": domain_type,
        "Agency": domain_info.federal_agency,
        "Organization name": domain_info.organization_name,
        "City": domain_info.city,
        "State": domain_info.state_territory,
        "AO": domain_info.ao,  # type: ignore
        "AO email": domain_info.authorizing_official.email if domain_info.authorizing_official else " ",
        "Security contact email": security_email,
        "Created at": domain.created_at,
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

def export_data_type_to_csv(csv_file):
    """
    All domains report with extra columns.
    This maps to the "All domain metadata" button.
    """

    writer = csv.writer(csv_file)
    # define columns to include in export
    columns = [
        "Domain name",
        "Status",
        "First ready on",
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

    domains = DomainInformation.objects.all().filter(**filter_condition).distinct()
    domains_count = domains.count()
    federal = domains.filter(generic_org_type=DomainRequest.OrganizationChoices.FEDERAL).distinct().count()
    interstate = domains.filter(generic_org_type=DomainRequest.OrganizationChoices.INTERSTATE).count()
    state_or_territory = (
        domains.filter(generic_org_type=DomainRequest.OrganizationChoices.STATE_OR_TERRITORY).distinct().count()
    )
    tribal = domains.filter(generic_org_type=DomainRequest.OrganizationChoices.TRIBAL).distinct().count()
    county = domains.filter(generic_org_type=DomainRequest.OrganizationChoices.COUNTY).distinct().count()
    city = domains.filter(generic_org_type=DomainRequest.OrganizationChoices.CITY).distinct().count()
    special_district = (
        domains.filter(generic_org_type=DomainRequest.OrganizationChoices.SPECIAL_DISTRICT).distinct().count()
    )
    school_district = (
        domains.filter(generic_org_type=DomainRequest.OrganizationChoices.SCHOOL_DISTRICT).distinct().count()
    )
    election_board = domains.filter(is_election_board=True).distinct().count()

    return [
        domains_count,
        federal,
        interstate,
        state_or_territory,
        tribal,
        county,
        city,
        special_district,
        school_district,
        election_board,
    ]


def get_sliced_requests(filter_condition):
    """Get filtered requests counts sliced by org type and election office."""
    requests = DomainRequest.objects.all().filter(**filter_condition).distinct()
    requests_count = requests.count()
    federal = requests.filter(generic_org_type=DomainRequest.OrganizationChoices.FEDERAL).distinct().count()
    interstate = requests.filter(generic_org_type=DomainRequest.OrganizationChoices.INTERSTATE).distinct().count()
    state_or_territory = (
        requests.filter(generic_org_type=DomainRequest.OrganizationChoices.STATE_OR_TERRITORY).distinct().count()
    )
    tribal = requests.filter(generic_org_type=DomainRequest.OrganizationChoices.TRIBAL).distinct().count()
    county = requests.filter(generic_org_type=DomainRequest.OrganizationChoices.COUNTY).distinct().count()
    city = requests.filter(generic_org_type=DomainRequest.OrganizationChoices.CITY).distinct().count()
    special_district = (
        requests.filter(generic_org_type=DomainRequest.OrganizationChoices.SPECIAL_DISTRICT).distinct().count()
    )
    school_district = (
        requests.filter(generic_org_type=DomainRequest.OrganizationChoices.SCHOOL_DISTRICT).distinct().count()
    )
    election_board = requests.filter(is_election_board=True).distinct().count()

    return [
        requests_count,
        federal,
        interstate,
        state_or_territory,
        tribal,
        county,
        city,
        special_district,
        school_district,
        election_board,
    ]


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


class DomainRequestExport:
    """
    A collection of functions which return csv files regarding the DomainRequest model.
    Purely organizational -- all functions are independent.
    """

    @staticmethod
    def write_csv_for_requests(
        writer,
        columns,
        requests,
        should_write_header=True,
    ):
        """Receives params from the parent methods and outputs a CSV with filtered and sorted requests.
        Works with write_header as long as the same writer object is passed."""

        # Reduce the memory overhead when performing the write operation
        paginator = Paginator(requests, 1000)
        total_body_rows = []

        for page_num in paginator.page_range:
            page = paginator.page(page_num)
            rows = []
            for request in page.object_list:
                try:
                    row = DomainRequestExport.parse_row_for_requests(columns, request)
                    rows.append(row)
                except ValueError as err:
                    logger.error(f"csv_export -> Error when parsing row: {err}")
                    continue
            total_body_rows.extend(rows)

        if should_write_header:
            write_header(writer, columns)
        writer.writerows(total_body_rows)
    
    @staticmethod
    def parse_row_for_requests(columns, request):
        """Given a set of columns, generate a new row from cleaned column data"""

        # create a dictionary of fields which can be included in output
        FIELDS = {
            "Domain request": request.get('requested_domain_name'),
            "Submitted at": request.get('submission_date'),  # TODO - different format?
            "Status": request.get('status_display'),
            "Domain type": request.get('domain_type'),
            "Federal type": request.get("human_readable_federal_type"),
            "Federal agency": request.get('federal_agency_name'),
            "Organization name": request.get('organization_name'),
            "Election office": request.get("human_readable_election_board"),
            "City": request.get('city'),
            "State/territory": request.get('state_territory'),
            "Region": None,  # TODO - what is this field?
            # Creator
            "Creator first name": request.get('creator__first_name', ""),
            "Creator last name": request.get('creator__last_name', ""),
            "Creator email": request.get('creator__email', ""),
            "Creator approved domains count": request.get("creator_approved_domains_count", 0),
            "Creator active requests count": request.get("creator_active_requests_count", 0),
            # End of creator
            "Alternative domains": request.get('all_alternative_domains'),
            # AO
            "AO first name": request.get('authorizing_official__first_name', ""),
            "AO last name":  request.get('authorizing_official__last_name', ""),
            "AO email": request.get('authorizing_official__email', ""),
            "AO title/role": request.get('authorizing_official__title', ""),
            # End of AO
            "Request purpose": request.get('purpose'),
            "Request additional details": request.get('additional_details'),
            "Other contacts": request.get('all_other_contacts'),
            "CISA regional representative": request.get('cisa_representative_email'),  # TODO - same problem as before
            "Current websites": request.get('all_current_websites'),
            "Investigator": request.get('investigator_email'),
        }

        row = [FIELDS.get(column, "") for column in columns]
        return row

    @staticmethod
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
            "Domain request",
            "Domain type",
            "Submitted at",
        ]

        sort_fields = [
            "requested_domain__name",
        ]
        filter_condition = {
            "status": DomainRequest.DomainRequestStatus.SUBMITTED,
            "submission_date__lte": end_date_formatted,
            "submission_date__gte": start_date_formatted,
        }

        all_requests = DomainRequest.objects.filter(**filter_condition).order_by(*sort_fields).distinct()

        # Convert the request to a querystring for faster processing. Only grab what we need.
        parsed_requests = all_requests.annotate(
            requested_domain_name=DomainRequestExport.get_requested_domain_name_query(),
            approved_domain_name=F('approved_domain__name'),
        ).values(
            "requested_domain_name",
            "generic_org_type",
            "federal_type",
            "submission_date"
        )

        # Set the domain_type field.
        # Relies on a python function, get_organization_type_display, so we have to
        # do this manually.

        for request in parsed_requests:
            # Handle the domain_type field. Defaults to the wrong variant.
            org_type = request.get("generic_org_type")
            federal_type = request.get("federal_type")

            request["domain_type"] = None
            if org_type:
                readable_org_type = DomainRequest.OrganizationChoices.get_org_label(org_type)
                if federal_type:
                    readable_federal_type = DomainRequest.BranchChoices.get_branch_label(federal_type)
                    request["domain_type"] = f"{readable_org_type} - {readable_federal_type}"
                else:
                    request["domain_type"] = readable_org_type

        DomainRequestExport.write_csv_for_requests(writer, columns, parsed_requests, should_write_header=True)

    @staticmethod
    def export_full_domain_request_report(csv_file):
        writer = csv.writer(csv_file)
        columns = [
            "Domain request",
            "Submitted at",
            "Status",
            "Domain type",
            "Federal type",
            "Federal agency",
            "Organization name",
            "Election office",
            "City",
            "State/territory",
            "Region",
            "Creator first name",
            "Creator last name",
            "Creator email",
            "Creator approved domains count",
            "Creator active requests count",
            "Alternative domains",
            "AO first name",
            "AO last name",
            "AO email",
            "AO title/role",
            "Request purpose",
            "Request additional details",
            "Other contacts",
            "CISA regional representative",
            "Current websites",
            "Investigator",
        ]
        excluded_statuses = [DomainRequest.DomainRequestStatus.STARTED]
        order_by = [
            "status",
            "requested_domain__name",
        ]
        requests = DomainRequest.objects.exclude(status__in=excluded_statuses).order_by(*order_by).distinct()
        parsed_requests = DomainRequestExport.annotate_and_prepare_domain_request_data(requests)

        DomainRequestExport.write_csv_for_requests(writer, columns, parsed_requests, should_write_header=True)

    @staticmethod
    def annotate_and_prepare_domain_request_data(requests_to_convert: QuerySet[DomainRequest]) -> QuerySet:
        """
        This function is designed to optimize performance by performing data manipulations directly in the database
        rather than in Python code, which is especially beneficial for operations on many-to-many fields.

        Args:
            requests_to_convert (QuerySet[DomainRequest]): A Django QuerySet of DomainRequest objects to be annotated.

        Returns:
            QuerySet: An annotated queryset that includes both original and annotated fields.

        Annotations (python-readable equivalents):
            - requested_domain_name: `requested_domain.name If requested_domain.name is not None else default_message`.
            - request_type: `f"{generic_org_type} | {federal_type}" If request.federal_type is not None else generic_org_type`.
            - additional_details: `f"{cisa_rep} | {anything_else}" If anything_else or cisa_rep else None`.
            - all_other_contacts: `[f"{c.first_name} {c.last_name} {c.email}" for c in request.other_contacts.all()].join(" | ")`.
            - all_current_websites: `# [w.website for w in request.current_websites.all()].join(" | ")`.
            - all_alternative_domains: `# [d.website for d in request.alternative_domains.all()].join(" | ")`.
        """  # noqa

        # As stated, this is equivalent to performing a bunch of if-statement like operations to
        # each of these fields inside a for loop. However, we want to avoid that for the sake
        # of performance - especially on many-to-many fields (which would require repeated DB calls in the loop).
        # By doing these operations in the DB, we save a lot of computation time.

        # We can do this for most fields, except ones that require us to grab .label (such as generic_org_type).
        # For those fields, they will otherwise just return the value representation so we parse those manually.

        parsed_requests = requests_to_convert.annotate(
            requested_domain_name=DomainRequestExport.get_requested_domain_name_query(),
            additional_details=DomainRequestExport.get_additional_details_query(),
            all_other_contacts=StringAgg(
                Concat('other_contacts__first_name', Value(' '), 'other_contacts__last_name', Value(' '), 'other_contacts__email'),
                delimiter=' | ',
                distinct=True
            ),
            all_current_websites=StringAgg('current_websites__website', delimiter=' | ', distinct=True),
            all_alternative_domains=StringAgg('alternative_domains__website', delimiter=' | ', distinct=True),

            # TODO - this is returning the wrong count
            creator_approved_domains_count=Count(
                'creator__domain_requests_created__id', 
                filter=Q(creator__domain_requests_created__status=DomainRequest.DomainRequestStatus.APPROVED),
                distinct=True
            ),
            # TODO - this is returning the wrong count
            creator_active_requests_count=Count(
                'creator__domain_requests_created__id', 
                filter=Q(creator__domain_requests_created__status__in=[
                    DomainRequest.DomainRequestStatus.SUBMITTED,
                    DomainRequest.DomainRequestStatus.IN_REVIEW,
                    DomainRequest.DomainRequestStatus.ACTION_NEEDED
                ]), 
                distinct=True
            ),
            federal_agency_name = F("federal_agency__agency"),
            investigator_email = F("investigator__email"),
            human_readable_election_board=Case(
                When(is_election_board=True, then=Value("Yes")),
                When(is_election_board=False, then=Value("No")),
                default=Value("N/A"),
                output_field=CharField()
            )
        )

        requests_dict = parsed_requests.values(
            # Custom fields
            "all_alternative_domains",
            'all_other_contacts', 
            'all_current_websites', 
            'additional_details',
            'requested_domain_name', 
            "federal_agency_name",
            "human_readable_election_board",
            # Creator
            'creator__first_name', 
            'creator__last_name', 
            'creator__email', 
            "creator_approved_domains_count",
            "creator_active_requests_count",
            # AO
            'authorizing_official__first_name',
            'authorizing_official__last_name', 
            'authorizing_official__email', 
            'authorizing_official__title',
            # Investigator
            "investigator_email",
            # Existing fields
            "id",
            'submission_date', 
            'status', 
            'federal_type',
            'organization_name', 
            'is_election_board', 
            'city', 
            'state_territory',
            'purpose', 
            'cisa_representative_email', 
            'investigator',
            "generic_org_type",
            "federal_type",
        )

        for request in requests_dict:
            # Handle the domain_type field. Defaults to the wrong format.
            org_type = request.get("generic_org_type")
            if org_type:
                readable_org_type = DomainRequest.OrganizationChoices.get_org_label(org_type)
                request["domain_type"] = readable_org_type
            
            # Handle the federal_type field. Defaults to the wrong format.
            federal_type = request.get("federal_type")
            if federal_type:
                request["human_readable_federal_type"] = DomainRequest.BranchChoices.get_branch_label(federal_type)
            
            # Handle the status field. Defaults to the wrong format.
            status = request.get("status")
            if status:
                request["status_display"] = DomainRequest.DomainRequestStatus.get_status_label(status)

        return requests_dict

    # ============================================================= #
    # Helper functions for django ORM queries.                      #
    # We are using these rather than pure python for speed reasons. #
    # ============================================================= #
    @staticmethod
    def get_requested_domain_name_query(default_message="No requested domain"):
        """
        A SQL case statement for DomainRequest.requested_domain.name.

        When ran, returns requested_domain.name if not null. Otherwise, returns default_message.

        Equivalent to: 

        `requested_domain.name If requested_domain.name is not None else default_message`
        """
        requested_domain_name_query = Case(
            When(
                requested_domain__isnull=False, 
                then=F('requested_domain__name')
            ),
            default=Value(default_message),
            output_field=CharField(),
        )

        return requested_domain_name_query

        
    @staticmethod
    def get_additional_details_query(default_message=None):
        """
        A SQL case statement for DomainRequest.anything_else and DomainRequest.cisa_representative_email.

        When ran, returns a concatenation of anything_else and cisa_representative_email - seperated by " | ".

        Equivalent to: 

        `f"{cisa_rep} | {anything_else}" If anything_else or cisa_rep else None`
        """

        # TODO this should be replaced with cisa_representative_first_name and cisa_representative_last_name
        # When that PR gets merged
        additional_details_query = Case(
            # Check if either cisa_representative_email or anything_else is not null
            # TODO - touch up on this
            When(
                cisa_representative_email__isnull=False,
                then=Concat(F('cisa_representative_email'), Value(' | '), F('anything_else'))
            ),
            When(
                anything_else__isnull=False,
                then=Concat(F('cisa_representative_email'), Value(' | '), F('anything_else'))
            ),
            default=Value(default_message),
            output_field=CharField(),
        )

        return additional_details_query
