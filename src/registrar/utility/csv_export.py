from collections import defaultdict
import csv
import logging
from datetime import datetime
from registrar.models import (
    Domain,
    DomainInvitation,
    DomainRequest,
    DomainInformation,
    PublicContact,
    UserDomainRole,
)
from django.db.models import QuerySet, Value, CharField, Count, Q, F
from django.db.models import ManyToManyField
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models.functions import Concat, Coalesce
from django.contrib.postgres.aggregates import StringAgg
from registrar.models.utility.generic_helper import convert_queryset_to_dict
from registrar.templatetags.custom_filters import get_region
from registrar.utility.enums import DefaultEmail
from registrar.utility.constants import BranchChoices


logger = logging.getLogger(__name__)


def write_header(writer, columns):
    """
    Receives params from the parent methods and outputs a CSV with a header row.
    Works with write_header as long as the same writer object is passed.
    """
    writer.writerow(columns)


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

class DomainExport:
    """
    A collection of functions which return csv files regarding the Domain model.
    """

    @classmethod
    def export_data_type_to_csv(cls, csv_file):
        """
        All domain metadata:
        Exports domains of all statuses plus domain managers.
        """
        writer = csv.writer(csv_file)
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
            "Domain managers",
            "Invited domain managers",
        ]

        # Coalesce is used to replace federal_type of None with ZZZZZ
        sort_fields = [
            "organization_type",
            Coalesce("federal_type", Value("ZZZZZ")),
            "federal_agency",
            "domain__name",
        ]

        # Fetch all relevant PublicContact entries
        public_contacts = cls.get_all_security_emails()

        # Fetch all relevant Invite entries
        domain_invitations = cls.get_all_domain_invitations()

        # Fetch all relevant ComainUserRole entries
        user_domain_roles = cls.get_all_user_domain_roles()

        domain_infos = (
            DomainInformation.objects.select_related("domain", "authorizing_official")
            .prefetch_related("permissions")
            .order_by(*sort_fields)
            .distinct()
        )

        annotations = cls._domain_metadata_annotations()

         # The .values returned from annotate_and_retrieve_fields can't go two levels deep
        # (just returns the field id of say, "creator") - so we have to include this.
        additional_values = [
            "domain__name",
            "domain__state",
            "domain__first_ready",
            "domain__expiration_date",
            "domain__created_at",
            "domain__deleted",
            "authorizing_official__email",
            "federal_agency__agency",
        ]

        # Convert the domain request queryset to a dictionary (including annotated fields)
        annotated_domains = cls.annotate_and_retrieve_fields(domain_infos, annotations, public_contacts, domain_invitations, user_domain_roles, additional_values)
        requests_dict = convert_queryset_to_dict(annotated_domains, is_model=False)

        # Write the csv file
        cls.write_csv_for_domains(writer, columns, requests_dict)

    @classmethod
    def export_data_full_to_csv(cls, csv_file):
        """Current full"""
        writer = csv.writer(csv_file)
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

        domain_infos = (
            DomainInformation.objects.select_related("domain")
            .filter(**filter_condition)
            .order_by(*sort_fields)
            .distinct()
        )

        annotations = {}
        additional_values = [
            "domain__name",
            "federal_agency__agency",
        ]
        
        # Convert the domain request queryset to a dictionary (including annotated fields)
        annotated_domains = cls.annotate_and_retrieve_fields(domain_infos, annotations, {}, {}, {}, additional_values)
        requests_dict = convert_queryset_to_dict(annotated_domains, is_model=False)

        # Write the csv file
        cls.write_csv_for_domains(writer, columns, requests_dict)

    @classmethod
    def export_data_federal_to_csv(cls, csv_file):
        """Current federal"""
        writer = csv.writer(csv_file)
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

        domain_infos = (
            DomainInformation.objects.select_related("domain")
            .filter(**filter_condition)
            .order_by(*sort_fields)
            .distinct()
        )

        annotations = {}
        additional_values = [
            "domain__name",
            "federal_agency__agency",
        ]
        
        # Convert the domain request queryset to a dictionary (including annotated fields)
        annotated_domains = cls.annotate_and_retrieve_fields(domain_infos, annotations, {}, {}, {}, additional_values)
        requests_dict = convert_queryset_to_dict(annotated_domains, is_model=False)

        # Write the csv file
        cls.write_csv_for_domains(writer, columns, requests_dict)

    @classmethod
    def export_data_domain_growth_to_csv(cls, csv_file, start_date, end_date):
        """
        Domain growth:
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

        domain_infos = (
            DomainInformation.objects.select_related("domain")
            .filter(**filter_condition)
            .order_by(*sort_fields)
            .distinct()
        )
        deleted_domain_infos = (
            DomainInformation.objects.select_related("domain")
            .filter(**filter_condition_for_deleted_domains)
            .order_by(*sort_fields_for_deleted_domains)
            .distinct()
        )

        annotations = {}
        additional_values = [
            "domain__name",
            "domain__state",
            "domain__first_ready",
            "domain__expiration_date",
            "domain__created_at",
            "domain__deleted",
            "federal_agency__agency",
        ]

        # Convert the domain request queryset to a dictionary (including annotated fields)
        annotated_domains = cls.annotate_and_retrieve_fields(domain_infos, annotations, {}, {}, {}, additional_values)
        requests_dict = convert_queryset_to_dict(annotated_domains, is_model=False)

        # Convert the domain request queryset to a dictionary (including annotated fields)
        deleted_annotated_domains = cls.annotate_and_retrieve_fields(deleted_domain_infos, annotations, {}, {}, {}, additional_values)
        deleted_requests_dict = convert_queryset_to_dict(deleted_annotated_domains, is_model=False)

        cls.write_csv_for_domains(
            writer, columns, requests_dict

        )
        cls.write_csv_for_domains(
            writer,
            columns,
            deleted_requests_dict,
            should_write_header=False,
        )   

    @classmethod
    def export_data_managed_domains_to_csv(cls, csv_file, start_date, end_date):
        """
        Managed domains:
        Get counts for domains that have domain managers for two different dates,
        get list of managed domains at end_date."""
        start_date_formatted = format_start_date(start_date)
        end_date_formatted = format_end_date(end_date)
        writer = csv.writer(csv_file)
        columns = [
            "Domain name",
            "Domain type",
            "Domain managers",
            "Invited domain managers",
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

        domain_invitations = cls.get_all_domain_invitations()

        # Fetch all relevant ComainUserRole entries
        user_domain_roles = cls.get_all_user_domain_roles()

        annotations = {}
         # The .values returned from annotate_and_retrieve_fields can't go two levels deep
        # (just returns the field id of say, "creator") - so we have to include this.
        additional_values = [
            "domain__name",
        ]

        domain_infos = (
            DomainInformation.objects.select_related("domain")
            .prefetch_related("permissions")
            .filter(**filter_managed_domains_end_date)
            .order_by(*sort_fields)
            .distinct()
        )

        # Convert the domain request queryset to a dictionary (including annotated fields)
        annotated_domains = cls.annotate_and_retrieve_fields(domain_infos, annotations, {}, domain_invitations, user_domain_roles, additional_values)
        requests_dict = convert_queryset_to_dict(annotated_domains, is_model=False)

        cls.write_csv_for_domains(
            writer,
            columns,
            requests_dict
        )

    @classmethod
    def export_data_unmanaged_domains_to_csv(cls, csv_file, start_date, end_date):
        """
        Unmanaged domains:
        Get counts for domains that have domain managers for two different dates,
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

        annotations = {}
         # The .values returned from annotate_and_retrieve_fields can't go two levels deep
        # (just returns the field id of say, "creator") - so we have to include this.
        additional_values = [
            "domain__name",
        ]
        domain_infos = (
            DomainInformation.objects.select_related("domain")
            .filter(**filter_unmanaged_domains_end_date)
            .order_by(*sort_fields)
            .distinct()
        )

        # Convert the domain request queryset to a dictionary (including annotated fields)
        annotated_domains = cls.annotate_and_retrieve_fields(domain_infos, annotations, {}, {}, {}, additional_values)
        requests_dict = convert_queryset_to_dict(annotated_domains, is_model=False)

        cls.write_csv_for_domains(
            writer,
            columns,
            requests_dict
        )

    @classmethod
    def _domain_metadata_annotations(cls, delimiter=", "):
        """"""
        return {
            "ao_name": Concat(
                Coalesce(F("authorizing_official__first_name"), Value("")),
                Value(" "),
                Coalesce(F("authorizing_official__last_name"), Value("")),
                output_field=CharField(),
            ),
        }

    @classmethod
    def annotate_and_retrieve_fields(
        cls, domains, annotations, public_contacts={}, domain_invitations={}, user_domain_roles={}, additional_values=None, include_many_to_many=False
    ) -> QuerySet:
        """
        Applies annotations to a queryset and retrieves specified fields,
        including class-defined and annotation-defined.

        Parameters:
            requests (QuerySet): Initial queryset.
            annotations (dict, optional): Fields to compute {field_name: expression}.
            additional_values (list, optional): Extra fields to retrieve; defaults to annotation keys if None.
            include_many_to_many (bool, optional): Determines if we should include many to many fields or not

        Returns:
            QuerySet: Contains dictionaries with the specified fields for each record.
        """

        if additional_values is None:
            additional_values = []

        # We can infer that if we're passing in annotations,
        # we want to grab the result of said annotation.
        if annotations:
            additional_values.extend(annotations.keys())

        # Get prexisting fields on DomainRequest
        domain_fields = set()
        for field in DomainInformation._meta.get_fields():
            # Exclude many to many fields unless we specify
            many_to_many = isinstance(field, ManyToManyField) and include_many_to_many
            if many_to_many or not isinstance(field, ManyToManyField):
                domain_fields.add(field.name)

        queryset = domains.annotate(**annotations).values(*domain_fields, *additional_values)
        annotated_domains = []

        # Create mapping of domain to a list of invited users and managers
        invited_users_dict = defaultdict(list)
        for domain, email in domain_invitations:
            invited_users_dict[domain].append(email)

        managers_dict = defaultdict(list)
        for domain, email in user_domain_roles:
            managers_dict[domain].append(email)

        # Annotate with security_contact from public_contacts
        for domain in queryset:
            domain['security_contact_email'] = public_contacts.get(domain.get('domain__registry_id'))
            domain['invited_users'] = ', '.join(invited_users_dict.get(domain.get('domain__name'), []))
            domain['managers'] = ', '.join(managers_dict.get(domain.get('domain__name'), []))
            annotated_domains.append(domain)

        if annotated_domains:
            return annotated_domains
        
        return queryset
    
    @staticmethod
    def parse_row_for_domains(columns, domain):
        """
        Given a set of columns and a request dictionary, generate a new row from cleaned column data.
        """

        status = domain.get("domain__state")
        human_readable_status = Domain.State.get_state_label(status)

        expiration_date = domain.get("domain__expiration_date")
        if expiration_date is None:
            expiration_date = "(blank)"

        first_ready_on = domain.get("domain__first_ready")
        if first_ready_on is None:
            first_ready_on = "(blank)"

        domain_org_type = domain.get("generic_org_type")
        human_readable_domain_org_type = DomainRequest.OrganizationChoices.get_org_label(domain_org_type)
        domain_federal_type = domain.get("federal_type")
        human_readable_domain_federal_type = BranchChoices.get_branch_label(domain_federal_type)
        domain_type = human_readable_domain_org_type
        if domain_federal_type and domain_org_type == DomainRequest.OrgChoicesElectionOffice.FEDERAL:
            domain_type = f"{human_readable_domain_org_type} - {human_readable_domain_federal_type}"

        if domain.get("domain__name") == "18f.gov":
            print(f'domain_type {domain_type}')
            print(f'federal_agency {domain.get("federal_agency")}')
            print(f'city {domain.get("city")}')

            print(f'agency {domain.get("agency")}')

            print(f'federal_agency__agency {domain.get("federal_agency__agency")}')

        # create a dictionary of fields which can be included in output.
        # "extra_fields" are precomputed fields (generated in the DB or parsed).
        FIELDS = {

            "Domain name": domain.get("domain__name"),
            "Status": human_readable_status,
            "First ready on": first_ready_on,
            "Expiration date": expiration_date,
            "Domain type": domain_type,
            "Agency": domain.get("federal_agency__agency"),
            "Organization name": domain.get("organization_name"),
            "City": domain.get("city"),
            "State": domain.get("state_territory"),
            "AO": domain.get("ao_name"),
            "AO email": domain.get("authorizing_official__email"),
            "Security contact email": domain.get("security_contact_email"),
            "Created at": domain.get("domain__created_at"),
            "Deleted": domain.get("domain__deleted"),
            "Domain managers": domain.get("managers"),
            "Invited domain managers": domain.get("invited_users"),
        }

        row = [FIELDS.get(column, "") for column in columns]
        return row

    @staticmethod
    def write_csv_for_domains(
        writer,
        columns,
        domains_dict,
        should_write_header=True,
    ):
        """Receives params from the parent methods and outputs a CSV with filtered and sorted requests.
        Works with write_header as long as the same writer object is passed."""

        rows = []
        for domain in domains_dict.values():
            try:
                row = DomainExport.parse_row_for_domains(columns, domain)
                rows.append(row)
            except ValueError as err:
                logger.error(f"csv_export -> Error when parsing row: {err}")
                continue

        if should_write_header:
            write_header(writer, columns)

        writer.writerows(rows)

    # ============================================================= #
    # Helper functions for django ORM queries.                      #
    # We are using these rather than pure python for speed reasons. #
    # ============================================================= #

    @classmethod
    def get_all_security_emails(cls):
        """
        Fetch all PublicContact entries and return a mapping of registry_id to email.
        """
        public_contacts = PublicContact.objects.values_list('registry_id', 'email')
        return {registry_id: email for registry_id, email in public_contacts}
    
    @classmethod
    def get_all_domain_invitations(cls):
        """
        Fetch all DomainInvitation entries and return a mapping of domain to email.
        """
        domain_invitations = DomainInvitation.objects.filter(status="invited").values_list('domain__name', 'email')
        return list(domain_invitations)

    @classmethod
    def get_all_user_domain_roles(cls):
        """
        Fetch all UserDomainRole entries and return a mapping of domain to user__email.
        """
        user_domain_roles = UserDomainRole.objects.select_related('user').values_list('domain__name', 'user__email')
        return list(user_domain_roles)



class DomainRequestExport:
    """
    A collection of functions which return csv files regarding the DomainRequest model.
    """

    # Get all columns on the full metadata report
    all_columns = [
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

    @classmethod
    def export_data_requests_growth_to_csv(cls, csv_file, start_date, end_date):
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
            "Federal type",
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

        # We don't want to annotate anything, but we do want to access the requested domain name
        annotations = {}
        additional_values = ["requested_domain__name"]

        all_requests = DomainRequest.objects.filter(**filter_condition).order_by(*sort_fields).distinct()

        annotated_requests = cls.annotate_and_retrieve_fields(all_requests, annotations, additional_values)
        requests_dict = convert_queryset_to_dict(annotated_requests, is_model=False)

        cls.write_csv_for_requests(writer, columns, requests_dict)

    @classmethod
    def export_full_domain_request_report(cls, csv_file):
        """
        Generates a detailed domain request report to a CSV file.

        Retrieves and annotates DomainRequest objects, excluding 'STARTED' status,
        with related data optimizations via select/prefetch and annotation.

        Annotated with counts and aggregates of related entities.
        Converts to dict and writes to CSV using predefined columns.

        Parameters:
            csv_file (file-like object): Target CSV file.
        """
        writer = csv.writer(csv_file)

        requests = (
            DomainRequest.objects.select_related(
                "creator", "authorizing_official", "federal_agency", "investigator", "requested_domain"
            )
            .prefetch_related("current_websites", "other_contacts", "alternative_domains")
            .exclude(status__in=[DomainRequest.DomainRequestStatus.STARTED])
            .order_by(
                "status",
                "requested_domain__name",
            )
            .distinct()
        )

        # Annotations are custom columns returned to the queryset (AKA: computed in the DB).
        annotations = cls._full_domain_request_annotations()

        # The .values returned from annotate_and_retrieve_fields can't go two levels deep
        # (just returns the field id of say, "creator") - so we have to include this.
        additional_values = [
            "requested_domain__name",
            "federal_agency__agency",
            "authorizing_official__first_name",
            "authorizing_official__last_name",
            "authorizing_official__email",
            "authorizing_official__title",
            "creator__first_name",
            "creator__last_name",
            "creator__email",
            "investigator__email",
        ]

        # Convert the domain request queryset to a dictionary (including annotated fields)
        annotated_requests = cls.annotate_and_retrieve_fields(requests, annotations, additional_values)
        requests_dict = convert_queryset_to_dict(annotated_requests, is_model=False)

        # Write the csv file
        cls.write_csv_for_requests(writer, cls.all_columns, requests_dict)

    @classmethod
    def _full_domain_request_annotations(cls, delimiter=" | "):
        """Returns the annotations for the full domain request report"""
        return {
            "creator_approved_domains_count": DomainRequestExport.get_creator_approved_domains_count_query(),
            "creator_active_requests_count": DomainRequestExport.get_creator_active_requests_count_query(),
            "all_current_websites": StringAgg("current_websites__website", delimiter=delimiter, distinct=True),
            "all_alternative_domains": StringAgg("alternative_domains__website", delimiter=delimiter, distinct=True),
            # Coerce the other contacts object to "{first_name} {last_name} {email}"
            "all_other_contacts": StringAgg(
                Concat(
                    "other_contacts__first_name",
                    Value(" "),
                    "other_contacts__last_name",
                    Value(" "),
                    "other_contacts__email",
                ),
                delimiter=delimiter,
                distinct=True,
            ),
        }

    @staticmethod
    def write_csv_for_requests(
        writer,
        columns,
        requests_dict,
        should_write_header=True,
    ):
        """Receives params from the parent methods and outputs a CSV with filtered and sorted requests.
        Works with write_header as long as the same writer object is passed."""

        rows = []
        for request in requests_dict.values():
            try:
                row = DomainRequestExport.parse_row_for_requests(columns, request)
                rows.append(row)
            except ValueError as err:
                logger.error(f"csv_export -> Error when parsing row: {err}")
                continue

        if should_write_header:
            write_header(writer, columns)

        writer.writerows(rows)

    @staticmethod
    def parse_row_for_requests(columns, request):
        """
        Given a set of columns and a request dictionary, generate a new row from cleaned column data.
        """

        # Handle the federal_type field. Defaults to the wrong format.
        federal_type = request.get("federal_type")
        human_readable_federal_type = BranchChoices.get_branch_label(federal_type) if federal_type else None

        # Handle the org_type field
        org_type = request.get("generic_org_type") or request.get("organization_type")
        human_readable_org_type = DomainRequest.OrganizationChoices.get_org_label(org_type) if org_type else None

        # Handle the status field. Defaults to the wrong format.
        status = request.get("status")
        status_display = DomainRequest.DomainRequestStatus.get_status_label(status) if status else None

        # Handle the region field.
        state_territory = request.get("state_territory")
        region = get_region(state_territory) if state_territory else None

        # Handle the requested_domain field (add a default if None)
        requested_domain = request.get("requested_domain__name")
        requested_domain_name = requested_domain if requested_domain else "No requested domain"

        # Handle the election field. N/A if None, "Yes"/"No" if boolean
        human_readable_election_board = "N/A"
        is_election_board = request.get("is_election_board")
        if is_election_board is not None:
            human_readable_election_board = "Yes" if is_election_board else "No"

        # Handle the additional details field. Pipe seperated.
        cisa_rep_first = request.get("cisa_representative_first_name")
        cisa_rep_last = request.get("cisa_representative_last_name")
        name = [n for n in [cisa_rep_first, cisa_rep_last] if n]

        cisa_rep = " ".join(name) if name else None
        details = [cisa_rep, request.get("anything_else")]
        additional_details = " | ".join([field for field in details if field])

        # create a dictionary of fields which can be included in output.
        # "extra_fields" are precomputed fields (generated in the DB or parsed).
        FIELDS = {
            # Parsed fields - defined above.
            "Domain request": requested_domain_name,
            "Region": region,
            "Status": status_display,
            "Election office": human_readable_election_board,
            "Federal type": human_readable_federal_type,
            "Domain type": human_readable_org_type,
            "Request additional details": additional_details,
            # Annotated fields - passed into the request dict.
            "Creator approved domains count": request.get("creator_approved_domains_count", 0),
            "Creator active requests count": request.get("creator_active_requests_count", 0),
            "Alternative domains": request.get("all_alternative_domains"),
            "Other contacts": request.get("all_other_contacts"),
            "Current websites": request.get("all_current_websites"),
            # Untouched FK fields - passed into the request dict.
            "Federal agency": request.get("federal_agency__agency"),
            "AO first name": request.get("authorizing_official__first_name"),
            "AO last name": request.get("authorizing_official__last_name"),
            "AO email": request.get("authorizing_official__email"),
            "AO title/role": request.get("authorizing_official__title"),
            "Creator first name": request.get("creator__first_name"),
            "Creator last name": request.get("creator__last_name"),
            "Creator email": request.get("creator__email"),
            "Investigator": request.get("investigator__email"),
            # Untouched fields
            "Organization name": request.get("organization_name"),
            "City": request.get("city"),
            "State/territory": request.get("state_territory"),
            "Request purpose": request.get("purpose"),
            "CISA regional representative": request.get("cisa_representative_email"),
            "Submitted at": request.get("submission_date"),
        }

        row = [FIELDS.get(column, "") for column in columns]
        return row

    @classmethod
    def annotate_and_retrieve_fields(
        cls, requests, annotations, additional_values=None, include_many_to_many=False
    ) -> QuerySet:
        """
        Applies annotations to a queryset and retrieves specified fields,
        including class-defined and annotation-defined.

        Parameters:
            requests (QuerySet): Initial queryset.
            annotations (dict, optional): Fields to compute {field_name: expression}.
            additional_values (list, optional): Extra fields to retrieve; defaults to annotation keys if None.
            include_many_to_many (bool, optional): Determines if we should include many to many fields or not

        Returns:
            QuerySet: Contains dictionaries with the specified fields for each record.
        """

        if additional_values is None:
            additional_values = []

        # We can infer that if we're passing in annotations,
        # we want to grab the result of said annotation.
        if annotations:
            additional_values.extend(annotations.keys())

        # Get prexisting fields on DomainRequest
        domain_request_fields = set()
        for field in DomainRequest._meta.get_fields():
            # Exclude many to many fields unless we specify
            many_to_many = isinstance(field, ManyToManyField) and include_many_to_many
            if many_to_many or not isinstance(field, ManyToManyField):
                domain_request_fields.add(field.name)

        queryset = requests.annotate(**annotations).values(*domain_request_fields, *additional_values)
        return queryset

    # ============================================================= #
    # Helper functions for django ORM queries.                      #
    # We are using these rather than pure python for speed reasons. #
    # ============================================================= #

    @staticmethod
    def get_creator_approved_domains_count_query():
        """
        Generates a Count query for distinct approved domain requests per creator.

        Returns:
            Count: Aggregates distinct 'APPROVED' domain requests by creator.
        """

        query = Count(
            "creator__domain_requests_created__id",
            filter=Q(creator__domain_requests_created__status=DomainRequest.DomainRequestStatus.APPROVED),
            distinct=True,
        )
        return query

    @staticmethod
    def get_creator_active_requests_count_query():
        """
        Generates a Count query for distinct approved domain requests per creator.

        Returns:
            Count: Aggregates distinct 'SUBMITTED', 'IN_REVIEW', and 'ACTION_NEEDED' domain requests by creator.
        """

        query = Count(
            "creator__domain_requests_created__id",
            filter=Q(
                creator__domain_requests_created__status__in=[
                    DomainRequest.DomainRequestStatus.SUBMITTED,
                    DomainRequest.DomainRequestStatus.IN_REVIEW,
                    DomainRequest.DomainRequestStatus.ACTION_NEEDED,
                ]
            ),
            distinct=True,
        )
        return query
