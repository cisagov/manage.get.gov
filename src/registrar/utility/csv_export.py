from abc import ABC, abstractmethod
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
from django.db.models import Case, CharField, Count, DateField, F, ManyToManyField, Q, QuerySet, Value, When
from django.utils import timezone
from django.db.models.functions import Concat, Coalesce
from django.contrib.postgres.aggregates import StringAgg
from registrar.models.utility.generic_helper import convert_queryset_to_dict
from registrar.templatetags.custom_filters import get_region
from registrar.utility.constants import BranchChoices
from registrar.utility.enums import DefaultEmail


logger = logging.getLogger(__name__)


def write_header(writer, columns):
    """
    Receives params from the parent methods and outputs a CSV with a header row.
    Works with write_header as long as the same writer object is passed.
    """
    writer.writerow(columns)


def get_default_start_date():
    """Default to a date that's prior to our first deployment"""
    return timezone.make_aware(datetime(2023, 11, 1))


def get_default_end_date():
    """Default to now()"""
    return timezone.now()


def format_start_date(start_date):
    return timezone.make_aware(datetime.strptime(start_date, "%Y-%m-%d")) if start_date else get_default_start_date()


def format_end_date(end_date):
    return timezone.make_aware(datetime.strptime(end_date, "%Y-%m-%d")) if end_date else get_default_end_date()


class BaseExport(ABC):
    """
    A generic class for exporting data which returns a csv file for the given model.
    Base class in an inheritance tree of 3.
    """

    @classmethod
    @abstractmethod
    def model(self):
        """
        Property to specify the model that the export class will handle.
        Must be implemented by subclasses.
        """
        pass

    @classmethod
    def get_columns(cls):
        """
        Returns the columns for CSV export. Override in subclasses as needed.
        """
        return []

    @classmethod
    def get_sort_fields(cls):
        """
        Returns the sort fields for the CSV export. Override in subclasses as needed.
        """
        return []

    @classmethod
    def get_additional_args(cls):
        """
        Returns additional keyword arguments as an empty dictionary.
        Override in subclasses to provide specific arguments.
        """
        return {}

    @classmethod
    def get_select_related(cls):
        """
        Get a list of tables to pass to select_related when building queryset.
        """
        return []

    @classmethod
    def get_prefetch_related(cls):
        """
        Get a list of tables to pass to prefetch_related when building queryset.
        """
        return []

    @classmethod
    def get_exclusions(cls):
        """
        Get a Q object of exclusion conditions to pass to .exclude() when building queryset.
        """
        return Q()

    @classmethod
    def get_filter_conditions(cls, **export_kwargs):
        """
        Get a Q object of filter conditions to filter when building queryset.
        """
        return Q()

    @classmethod
    def get_computed_fields(cls):
        """
        Get a dict of computed fields. These are fields that do not exist on the model normally
        and will be passed to .annotate() when building a queryset.
        """
        return {}

    @classmethod
    def get_annotations_for_sort(cls):
        """
        Get a dict of annotations to make available for order_by clause.
        """
        return {}

    @classmethod
    def get_related_table_fields(cls):
        """
        Get a list of fields from related tables.
        """
        return []

    @classmethod
    def update_queryset(cls, queryset, **kwargs):
        """
        Returns an updated queryset. Override in subclass to update queryset.
        """
        return queryset

    @classmethod
    def write_csv_before(cls, csv_writer, **export_kwargs):
        """
        Write to csv file before the write_csv method.
        Override in subclasses where needed.
        """
        pass

    @classmethod
    def annotate_and_retrieve_fields(
        cls, initial_queryset, computed_fields, related_table_fields=None, include_many_to_many=False, **kwargs
    ) -> QuerySet:
        """
        Applies annotations to a queryset and retrieves specified fields,
        including class-defined and annotation-defined.

        Parameters:
            initial_queryset (QuerySet): Initial queryset.
            computed_fields (dict, optional): Fields to compute {field_name: expression}.
            related_table_fields (list, optional): Extra fields to retrieve; defaults to annotation keys if None.
            include_many_to_many (bool, optional): Determines if we should include many to many fields or not
            **kwargs: Additional keyword arguments for specific parameters (e.g., public_contacts, domain_invitations,
                  user_domain_roles).

        Returns:
            QuerySet: Contains dictionaries with the specified fields for each record.
        """
        if related_table_fields is None:
            related_table_fields = []

        # We can infer that if we're passing in annotations,
        # we want to grab the result of said annotation.
        if computed_fields:
            related_table_fields.extend(computed_fields.keys())

        # Get prexisting fields on the model
        model_fields = set()
        for field in cls.model()._meta.get_fields():
            # Exclude many to many fields unless we specify
            many_to_many = isinstance(field, ManyToManyField) and include_many_to_many
            if many_to_many or not isinstance(field, ManyToManyField):
                model_fields.add(field.name)

        queryset = initial_queryset.annotate(**computed_fields).values(*model_fields, *related_table_fields)

        return cls.update_queryset(queryset, **kwargs)

    @classmethod
    def export_data_to_csv(cls, csv_file, **export_kwargs):
        """
        All domain metadata:
        Exports domains of all statuses plus domain managers.
        """
        writer = csv.writer(csv_file)
        columns = cls.get_columns()
        sort_fields = cls.get_sort_fields()
        kwargs = cls.get_additional_args()
        select_related = cls.get_select_related()
        prefetch_related = cls.get_prefetch_related()
        exclusions = cls.get_exclusions()
        annotations_for_sort = cls.get_annotations_for_sort()
        filter_conditions = cls.get_filter_conditions(**export_kwargs)
        computed_fields = cls.get_computed_fields()
        related_table_fields = cls.get_related_table_fields()

        model_queryset = (
            cls.model()
            .objects.select_related(*select_related)
            .prefetch_related(*prefetch_related)
            .filter(filter_conditions)
            .exclude(exclusions)
            .annotate(**annotations_for_sort)
            .order_by(*sort_fields)
            .distinct()
        )

        # Convert the queryset to a dictionary (including annotated fields)
        annotated_queryset = cls.annotate_and_retrieve_fields(
            model_queryset, computed_fields, related_table_fields, **kwargs
        )
        models_dict = convert_queryset_to_dict(annotated_queryset, is_model=False)

        # Write to csv file before the write_csv
        cls.write_csv_before(writer, **export_kwargs)

        # Write the csv file
        rows = cls.write_csv(writer, columns, models_dict)

        # Return rows that for easier parsing and testing
        return rows

    @classmethod
    def write_csv(
        cls,
        writer,
        columns,
        models_dict,
        should_write_header=True,
    ):
        """Receives params from the parent methods and outputs a CSV with filtered and sorted objects.
        Works with write_header as long as the same writer object is passed."""

        rows = []
        for object in models_dict.values():
            try:
                row = cls.parse_row(columns, object)
                rows.append(row)
            except ValueError as err:
                logger.error(f"csv_export -> Error when parsing row: {err}")
                continue

        if should_write_header:
            write_header(writer, columns)

        writer.writerows(rows)

        # Return rows for easier parsing and testing
        return rows

    @classmethod
    @abstractmethod
    def parse_row(cls, columns, model):
        """
        Given a set of columns and a model dictionary, generate a new row from cleaned column data.
        Must be implemented by subclasses
        """
        pass


class DomainExport(BaseExport):
    """
    A collection of functions which return csv files regarding Domains.  Although class is
    named DomainExport, the base model for the export is DomainInformation.
    Second class in an inheritance tree of 3.
    """

    @classmethod
    def model(cls):
        # Return the model class that this export handles
        return DomainInformation

    @classmethod
    def update_queryset(cls, queryset, **kwargs):
        """
        Returns an updated queryset.

        Add security_contact_email, invited_users, and managers to the queryset,
        based on public_contacts, domain_invitations and user_domain_roles
        passed through kwargs.
        """
        public_contacts = kwargs.get("public_contacts", {})
        domain_invitations = kwargs.get("domain_invitations", {})
        user_domain_roles = kwargs.get("user_domain_roles", {})

        annotated_domain_infos = []

        # Create mapping of domain to a list of invited users and managers
        invited_users_dict = defaultdict(list)
        for domain, email in domain_invitations:
            invited_users_dict[domain].append(email)

        managers_dict = defaultdict(list)
        for domain, email in user_domain_roles:
            managers_dict[domain].append(email)

        # Annotate with security_contact from public_contacts, invited users
        # from domain_invitations, and managers from user_domain_roles
        for domain_info in queryset:
            domain_info["security_contact_email"] = public_contacts.get(
                domain_info.get("domain__security_contact_registry_id")
            )
            domain_info["invited_users"] = ", ".join(invited_users_dict.get(domain_info.get("domain__name"), []))
            domain_info["managers"] = ", ".join(managers_dict.get(domain_info.get("domain__name"), []))
            annotated_domain_infos.append(domain_info)

        if annotated_domain_infos:
            return annotated_domain_infos

        return queryset

    # ============================================================= #
    # Helper functions for django ORM queries.                      #
    # We are using these rather than pure python for speed reasons. #
    # ============================================================= #

    @classmethod
    def get_all_security_emails(cls):
        """
        Fetch all PublicContact entries and return a mapping of registry_id to email.
        """
        public_contacts = PublicContact.objects.values_list("registry_id", "email")
        return {registry_id: email for registry_id, email in public_contacts}

    @classmethod
    def get_all_domain_invitations(cls):
        """
        Fetch all DomainInvitation entries and return a mapping of domain to email.
        """
        domain_invitations = DomainInvitation.objects.filter(status="invited").values_list("domain__name", "email")
        return list(domain_invitations)

    @classmethod
    def get_all_user_domain_roles(cls):
        """
        Fetch all UserDomainRole entries and return a mapping of domain to user__email.
        """
        user_domain_roles = (
            UserDomainRole.objects.select_related("user")
            .order_by("domain__name", "user__email")
            .values_list("domain__name", "user__email")
        )
        return list(user_domain_roles)

    @classmethod
    def parse_row(cls, columns, model):
        """
        Given a set of columns and a model dictionary, generate a new row from cleaned column data.
        """

        status = model.get("domain__state")
        human_readable_status = Domain.State.get_state_label(status)

        expiration_date = model.get("domain__expiration_date")
        if expiration_date is None:
            expiration_date = "(blank)"

        first_ready_on = model.get("domain__first_ready")
        if first_ready_on is None:
            first_ready_on = "(blank)"

        # organization_type has generic_org_type AND is_election
        domain_org_type = model.get("organization_type")
        human_readable_domain_org_type = DomainRequest.OrgChoicesElectionOffice.get_org_label(domain_org_type)
        domain_federal_type = model.get("federal_type")
        human_readable_domain_federal_type = BranchChoices.get_branch_label(domain_federal_type)
        domain_type = human_readable_domain_org_type
        if domain_federal_type and domain_org_type == DomainRequest.OrgChoicesElectionOffice.FEDERAL:
            domain_type = f"{human_readable_domain_org_type} - {human_readable_domain_federal_type}"

        security_contact_email = model.get("security_contact_email")
        invalid_emails = {DefaultEmail.LEGACY_DEFAULT.value, DefaultEmail.PUBLIC_CONTACT_DEFAULT.value}
        if (
            not security_contact_email
            or not isinstance(security_contact_email, str)
            or security_contact_email.lower().strip() in invalid_emails
        ):
            security_contact_email = "(blank)"

        # create a dictionary of fields which can be included in output.
        # "extra_fields" are precomputed fields (generated in the DB or parsed).
        FIELDS = {
            "Domain name": model.get("domain__name"),
            "Status": human_readable_status,
            "First ready on": first_ready_on,
            "Expiration date": expiration_date,
            "Domain type": domain_type,
            "Agency": model.get("federal_agency__agency"),
            "Organization name": model.get("organization_name"),
            "City": model.get("city"),
            "State": model.get("state_territory"),
            "SO": model.get("so_name"),
            "SO email": model.get("senior_official__email"),
            "Security contact email": security_contact_email,
            "Created at": model.get("domain__created_at"),
            "Deleted": model.get("domain__deleted"),
            "Domain managers": model.get("managers"),
            "Invited domain managers": model.get("invited_users"),
        }

        row = [FIELDS.get(column, "") for column in columns]
        return row

    @classmethod
    def get_sliced_domains(cls, filter_condition):
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


class DomainDataType(DomainExport):
    """
    Shows security contacts, domain managers, so
    Inherits from BaseExport -> DomainExport
    """

    @classmethod
    def get_columns(cls):
        """
        Overrides the columns for CSV export specific to DomainExport.
        """
        return [
            "Domain name",
            "Status",
            "First ready on",
            "Expiration date",
            "Domain type",
            "Agency",
            "Organization name",
            "City",
            "State",
            "SO",
            "SO email",
            "Security contact email",
            "Domain managers",
            "Invited domain managers",
        ]

    @classmethod
    def get_sort_fields(cls):
        """
        Returns the sort fields.
        """
        # Coalesce is used to replace federal_type of None with ZZZZZ
        return [
            "organization_type",
            Coalesce("federal_type", Value("ZZZZZ")),
            "federal_agency",
            "domain__name",
        ]

    @classmethod
    def get_additional_args(cls):
        """
        Returns additional keyword arguments specific to DomainExport.

        Returns:
            dict: Dictionary containing public_contacts, domain_invitations, and user_domain_roles.
        """
        # Fetch all relevant PublicContact entries
        public_contacts = cls.get_all_security_emails()

        # Fetch all relevant Invite entries
        domain_invitations = cls.get_all_domain_invitations()

        # Fetch all relevant UserDomainRole entries
        user_domain_roles = cls.get_all_user_domain_roles()

        return {
            "public_contacts": public_contacts,
            "domain_invitations": domain_invitations,
            "user_domain_roles": user_domain_roles,
        }

    @classmethod
    def get_select_related(cls):
        """
        Get a list of tables to pass to select_related when building queryset.
        """
        return ["domain", "senior_official"]

    @classmethod
    def get_prefetch_related(cls):
        """
        Get a list of tables to pass to prefetch_related when building queryset.
        """
        return ["permissions"]

    @classmethod
    def get_computed_fields(cls, delimiter=", "):
        """
        Get a dict of computed fields.
        """
        return {
            "so_name": Concat(
                Coalesce(F("senior_official__first_name"), Value("")),
                Value(" "),
                Coalesce(F("senior_official__last_name"), Value("")),
                output_field=CharField(),
            ),
        }

    @classmethod
    def get_related_table_fields(cls):
        """
        Get a list of fields from related tables.
        """
        return [
            "domain__name",
            "domain__state",
            "domain__first_ready",
            "domain__expiration_date",
            "domain__created_at",
            "domain__deleted",
            "domain__security_contact_registry_id",
            "senior_official__email",
            "federal_agency__agency",
        ]


class DomainDataTypeUser(DomainDataType):
    """
    The DomainDataType report, but sliced on the current request user
    """

    @classmethod
    def get_filter_conditions(cls, request=None):
        """
        Get a Q object of filter conditions to filter when building queryset.
        """
        if request is None or not hasattr(request, "user") or not request.user:
            # Return nothing
            return Q(id__in=[])
        else:
            # Get all domains the user is associated with
            return Q(domain__id__in=request.user.get_user_domain_ids(request))


class DomainDataFull(DomainExport):
    """
    Shows security contacts, filtered by state
    Inherits from BaseExport -> DomainExport
    """

    @classmethod
    def get_columns(cls):
        """
        Overrides the columns for CSV export specific to DomainExport.
        """
        return [
            "Domain name",
            "Domain type",
            "Agency",
            "Organization name",
            "City",
            "State",
            "Security contact email",
        ]

    @classmethod
    def get_sort_fields(cls):
        """
        Returns the sort fields.
        """
        # Coalesce is used to replace federal_type of None with ZZZZZ
        return [
            "organization_type",
            Coalesce("federal_type", Value("ZZZZZ")),
            "federal_agency",
            "domain__name",
        ]

    @classmethod
    def get_additional_args(cls):
        """
        Returns additional keyword arguments specific to DomainExport.

        Returns:
            dict: Dictionary containing public_contacts, domain_invitations, and user_domain_roles.
        """
        # Fetch all relevant PublicContact entries
        public_contacts = cls.get_all_security_emails()

        return {
            "public_contacts": public_contacts,
        }

    @classmethod
    def get_select_related(cls):
        """
        Get a list of tables to pass to select_related when building queryset.
        """
        return ["domain"]

    @classmethod
    def get_filter_conditions(cls):
        """
        Get a Q object of filter conditions to filter when building queryset.
        """
        return Q(
            domain__state__in=[
                Domain.State.READY,
                Domain.State.DNS_NEEDED,
                Domain.State.ON_HOLD,
            ],
        )

    @classmethod
    def get_computed_fields(cls, delimiter=", "):
        """
        Get a dict of computed fields.
        """
        return {
            "so_name": Concat(
                Coalesce(F("senior_official__first_name"), Value("")),
                Value(" "),
                Coalesce(F("senior_official__last_name"), Value("")),
                output_field=CharField(),
            ),
        }

    @classmethod
    def get_related_table_fields(cls):
        """
        Get a list of fields from related tables.
        """
        return [
            "domain__name",
            "domain__security_contact_registry_id",
            "federal_agency__agency",
        ]


class DomainDataFederal(DomainExport):
    """
    Shows security contacts, filtered by state and org type
    Inherits from BaseExport -> DomainExport
    """

    @classmethod
    def get_columns(cls):
        """
        Overrides the columns for CSV export specific to DomainExport.
        """
        return [
            "Domain name",
            "Domain type",
            "Agency",
            "Organization name",
            "City",
            "State",
            "Security contact email",
        ]

    @classmethod
    def get_sort_fields(cls):
        """
        Returns the sort fields.
        """
        # Coalesce is used to replace federal_type of None with ZZZZZ
        return [
            "organization_type",
            Coalesce("federal_type", Value("ZZZZZ")),
            "federal_agency",
            "domain__name",
        ]

    @classmethod
    def get_additional_args(cls):
        """
        Returns additional keyword arguments specific to DomainExport.

        Returns:
            dict: Dictionary containing public_contacts, domain_invitations, and user_domain_roles.
        """
        # Fetch all relevant PublicContact entries
        public_contacts = cls.get_all_security_emails()

        return {
            "public_contacts": public_contacts,
        }

    @classmethod
    def get_select_related(cls):
        """
        Get a list of tables to pass to select_related when building queryset.
        """
        return ["domain"]

    @classmethod
    def get_filter_conditions(cls):
        """
        Get a Q object of filter conditions to filter when building queryset.
        """
        return Q(
            organization_type__icontains="federal",
            domain__state__in=[
                Domain.State.READY,
                Domain.State.DNS_NEEDED,
                Domain.State.ON_HOLD,
            ],
        )

    @classmethod
    def get_computed_fields(cls, delimiter=", "):
        """
        Get a dict of computed fields.
        """
        return {
            "so_name": Concat(
                Coalesce(F("senior_official__first_name"), Value("")),
                Value(" "),
                Coalesce(F("senior_official__last_name"), Value("")),
                output_field=CharField(),
            ),
        }

    @classmethod
    def get_related_table_fields(cls):
        """
        Get a list of fields from related tables.
        """
        return [
            "domain__name",
            "domain__security_contact_registry_id",
            "federal_agency__agency",
        ]


class DomainGrowth(DomainExport):
    """
    Shows ready and deleted domains within a date range, sorted
    Inherits from BaseExport -> DomainExport
    """

    @classmethod
    def get_columns(cls):
        """
        Overrides the columns for CSV export specific to DomainExport.
        """
        return [
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

    @classmethod
    def get_annotations_for_sort(cls, delimiter=", "):
        """
        Get a dict of annotations to make available for sorting.
        """
        today = timezone.now().date()
        return {
            "custom_sort": Case(
                When(domain__state=Domain.State.READY, then="domain__first_ready"),
                When(domain__state=Domain.State.DELETED, then="domain__deleted"),
                default=Value(today),  # Default value if no conditions match
                output_field=DateField(),
            )
        }

    @classmethod
    def get_sort_fields(cls):
        """
        Returns the sort fields.
        """
        return [
            "-domain__state",
            "custom_sort",
            "domain__name",
        ]

    @classmethod
    def get_select_related(cls):
        """
        Get a list of tables to pass to select_related when building queryset.
        """
        return ["domain"]

    @classmethod
    def get_filter_conditions(cls, start_date=None, end_date=None):
        """
        Get a Q object of filter conditions to filter when building queryset.
        """
        filter_ready = Q(
            domain__state__in=[Domain.State.READY],
            domain__first_ready__gte=start_date,
            domain__first_ready__lte=end_date,
        )
        filter_deleted = Q(
            domain__state__in=[Domain.State.DELETED], domain__deleted__gte=start_date, domain__deleted__lte=end_date
        )
        return filter_ready | filter_deleted

    @classmethod
    def get_related_table_fields(cls):
        """
        Get a list of fields from related tables.
        """
        return [
            "domain__name",
            "domain__state",
            "domain__first_ready",
            "domain__expiration_date",
            "domain__created_at",
            "domain__deleted",
            "federal_agency__agency",
        ]


class DomainManaged(DomainExport):
    """
    Shows managed domains by an end date, sorted
    Inherits from BaseExport -> DomainExport
    """

    @classmethod
    def get_columns(cls):
        """
        Overrides the columns for CSV export specific to DomainExport.
        """
        return [
            "Domain name",
            "Domain type",
            "Domain managers",
            "Invited domain managers",
        ]

    @classmethod
    def get_sort_fields(cls):
        """
        Returns the sort fields.
        """
        return [
            "domain__name",
        ]

    @classmethod
    def get_select_related(cls):
        """
        Get a list of tables to pass to select_related when building queryset.
        """
        return ["domain"]

    @classmethod
    def get_prefetch_related(cls):
        """
        Get a list of tables to pass to prefetch_related when building queryset.
        """
        return ["permissions"]

    @classmethod
    def get_filter_conditions(cls, start_date=None, end_date=None):
        """
        Get a Q object of filter conditions to filter when building queryset.
        """
        end_date_formatted = format_end_date(end_date)
        return Q(
            domain__permissions__isnull=False,
            domain__first_ready__lte=end_date_formatted,
        )

    @classmethod
    def get_additional_args(cls):
        """
        Returns additional keyword arguments specific to DomainExport.

        Returns:
            dict: Dictionary containing public_contacts, domain_invitations, and user_domain_roles.
        """

        # Fetch all relevant Invite entries
        domain_invitations = cls.get_all_domain_invitations()

        # Fetch all relevant UserDomainRole entries
        user_domain_roles = cls.get_all_user_domain_roles()

        return {
            "domain_invitations": domain_invitations,
            "user_domain_roles": user_domain_roles,
        }

    @classmethod
    def get_related_table_fields(cls):
        """
        Get a list of fields from related tables.
        """
        return [
            "domain__name",
        ]

    @classmethod
    def write_csv_before(cls, csv_writer, start_date=None, end_date=None):
        """
        Write to csv file before the write_csv method.
        """
        start_date_formatted = format_start_date(start_date)
        end_date_formatted = format_end_date(end_date)
        filter_managed_domains_start_date = {
            "domain__permissions__isnull": False,
            "domain__first_ready__lte": start_date_formatted,
        }
        managed_domains_sliced_at_start_date = cls.get_sliced_domains(filter_managed_domains_start_date)

        csv_writer.writerow(["MANAGED DOMAINS COUNTS AT START DATE"])
        csv_writer.writerow(
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
        csv_writer.writerow(managed_domains_sliced_at_start_date)
        csv_writer.writerow([])

        filter_managed_domains_end_date = {
            "domain__permissions__isnull": False,
            "domain__first_ready__lte": end_date_formatted,
        }
        managed_domains_sliced_at_end_date = cls.get_sliced_domains(filter_managed_domains_end_date)

        csv_writer.writerow(["MANAGED DOMAINS COUNTS AT END DATE"])
        csv_writer.writerow(
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
        csv_writer.writerow(managed_domains_sliced_at_end_date)
        csv_writer.writerow([])


class DomainUnmanaged(DomainExport):
    """
    Shows unmanaged domains by an end date, sorted
    Inherits from BaseExport -> DomainExport
    """

    @classmethod
    def get_columns(cls):
        """
        Overrides the columns for CSV export specific to DomainExport.
        """
        return [
            "Domain name",
            "Domain type",
        ]

    @classmethod
    def get_sort_fields(cls):
        """
        Returns the sort fields.
        """
        return [
            "domain__name",
        ]

    @classmethod
    def get_select_related(cls):
        """
        Get a list of tables to pass to select_related when building queryset.
        """
        return ["domain"]

    @classmethod
    def get_prefetch_related(cls):
        """
        Get a list of tables to pass to prefetch_related when building queryset.
        """
        return ["permissions"]

    @classmethod
    def get_filter_conditions(cls, start_date=None, end_date=None):
        """
        Get a Q object of filter conditions to filter when building queryset.
        """
        end_date_formatted = format_end_date(end_date)
        return Q(
            domain__permissions__isnull=True,
            domain__first_ready__lte=end_date_formatted,
        )

    @classmethod
    def get_related_table_fields(cls):
        """
        Get a list of fields from related tables.
        """
        return [
            "domain__name",
        ]

    @classmethod
    def write_csv_before(cls, csv_writer, start_date=None, end_date=None):
        """
        Write to csv file before the write_csv method.

        """
        start_date_formatted = format_start_date(start_date)
        end_date_formatted = format_end_date(end_date)
        filter_unmanaged_domains_start_date = {
            "domain__permissions__isnull": True,
            "domain__first_ready__lte": start_date_formatted,
        }
        unmanaged_domains_sliced_at_start_date = cls.get_sliced_domains(filter_unmanaged_domains_start_date)

        csv_writer.writerow(["UNMANAGED DOMAINS AT START DATE"])
        csv_writer.writerow(
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
        csv_writer.writerow(unmanaged_domains_sliced_at_start_date)
        csv_writer.writerow([])

        filter_unmanaged_domains_end_date = {
            "domain__permissions__isnull": True,
            "domain__first_ready__lte": end_date_formatted,
        }
        unmanaged_domains_sliced_at_end_date = cls.get_sliced_domains(filter_unmanaged_domains_end_date)

        csv_writer.writerow(["UNMANAGED DOMAINS AT END DATE"])
        csv_writer.writerow(
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
        csv_writer.writerow(unmanaged_domains_sliced_at_end_date)
        csv_writer.writerow([])


class DomainRequestExport(BaseExport):
    """
    A collection of functions which return csv files regarding the DomainRequest model.
    Second class in an inheritance tree of 3.
    """

    @classmethod
    def model(cls):
        # Return the model class that this export handles
        return DomainRequest

    @classmethod
    def get_sliced_requests(cls, filter_condition):
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

    @classmethod
    def parse_row(cls, columns, model):
        """
        Given a set of columns and a model dictionary, generate a new row from cleaned column data.
        """

        # Handle the federal_type field. Defaults to the wrong format.
        federal_type = model.get("federal_type")
        human_readable_federal_type = BranchChoices.get_branch_label(federal_type) if federal_type else None

        # Handle the org_type field
        org_type = model.get("generic_org_type") or model.get("organization_type")
        human_readable_org_type = DomainRequest.OrganizationChoices.get_org_label(org_type) if org_type else None

        # Handle the status field. Defaults to the wrong format.
        status = model.get("status")
        status_display = DomainRequest.DomainRequestStatus.get_status_label(status) if status else None

        # Handle the region field.
        state_territory = model.get("state_territory")
        region = get_region(state_territory) if state_territory else None

        # Handle the requested_domain field (add a default if None)
        requested_domain = model.get("requested_domain__name")
        requested_domain_name = requested_domain if requested_domain else "No requested domain"

        # Handle the election field. N/A if None, "Yes"/"No" if boolean
        human_readable_election_board = "N/A"
        is_election_board = model.get("is_election_board")
        if is_election_board is not None:
            human_readable_election_board = "Yes" if is_election_board else "No"

        # Handle the additional details field. Pipe seperated.
        cisa_rep_first = model.get("cisa_representative_first_name")
        cisa_rep_last = model.get("cisa_representative_last_name")
        name = [n for n in [cisa_rep_first, cisa_rep_last] if n]

        cisa_rep = " ".join(name) if name else None
        details = [cisa_rep, model.get("anything_else")]
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
            "Creator approved domains count": model.get("creator_approved_domains_count", 0),
            "Creator active requests count": model.get("creator_active_requests_count", 0),
            "Alternative domains": model.get("all_alternative_domains"),
            "Other contacts": model.get("all_other_contacts"),
            "Current websites": model.get("all_current_websites"),
            # Untouched FK fields - passed into the request dict.
            "Federal agency": model.get("federal_agency__agency"),
            "SO first name": model.get("senior_official__first_name"),
            "SO last name": model.get("senior_official__last_name"),
            "SO email": model.get("senior_official__email"),
            "SO title/role": model.get("senior_official__title"),
            "Creator first name": model.get("creator__first_name"),
            "Creator last name": model.get("creator__last_name"),
            "Creator email": model.get("creator__email"),
            "Investigator": model.get("investigator__email"),
            # Untouched fields
            "Organization name": model.get("organization_name"),
            "City": model.get("city"),
            "State/territory": model.get("state_territory"),
            "Request purpose": model.get("purpose"),
            "CISA regional representative": model.get("cisa_representative_email"),
            "Last submitted date": model.get("last_submitted_date"),
            "First submitted date": model.get("first_submitted_date"),
            "Last status update": model.get("last_status_update"),
        }

        row = [FIELDS.get(column, "") for column in columns]
        return row


class DomainRequestGrowth(DomainRequestExport):
    """
    Shows submitted requests within a date range, sorted
    Inherits from BaseExport -> DomainRequestExport
    """

    @classmethod
    def get_columns(cls):
        """
        Overrides the columns for CSV export specific to DomainRequestGrowth.
        """
        return [
            "Domain request",
            "Domain type",
            "Federal type",
            "Submitted at",
        ]

    @classmethod
    def get_sort_fields(cls):
        """
        Returns the sort fields.
        """
        return [
            "requested_domain__name",
        ]

    @classmethod
    def get_filter_conditions(cls, start_date=None, end_date=None):
        """
        Get a Q object of filter conditions to filter when building queryset.
        """

        start_date_formatted = format_start_date(start_date)
        end_date_formatted = format_end_date(end_date)
        return Q(
            status=DomainRequest.DomainRequestStatus.SUBMITTED,
            last_submitted_date__lte=end_date_formatted,
            last_submitted_date__gte=start_date_formatted,
        )

    @classmethod
    def get_related_table_fields(cls):
        """
        Get a list of fields from related tables.
        """
        return ["requested_domain__name"]


class DomainRequestDataFull(DomainRequestExport):
    """
    Shows all but STARTED requests
    Inherits from BaseExport -> DomainRequestExport
    """

    @classmethod
    def get_columns(cls):
        """
        Overrides the columns for CSV export specific to DomainRequestGrowth.
        """
        return [
            "Domain request",
            "Last submitted date",
            "First submitted date",
            "Last status update",
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
            "SO first name",
            "SO last name",
            "SO email",
            "SO title/role",
            "Request purpose",
            "Request additional details",
            "Other contacts",
            "CISA regional representative",
            "Current websites",
            "Investigator",
        ]

    @classmethod
    def get_select_related(cls):
        """
        Get a list of tables to pass to select_related when building queryset.
        """
        return ["creator", "senior_official", "federal_agency", "investigator", "requested_domain"]

    @classmethod
    def get_prefetch_related(cls):
        """
        Get a list of tables to pass to prefetch_related when building queryset.
        """
        return ["current_websites", "other_contacts", "alternative_domains"]

    @classmethod
    def get_exclusions(cls):
        """
        Get a Q object of exclusion conditions to use when building queryset.
        """
        return Q(status__in=[DomainRequest.DomainRequestStatus.STARTED])

    @classmethod
    def get_sort_fields(cls):
        """
        Returns the sort fields.
        """
        return [
            "status",
            "requested_domain__name",
        ]

    @classmethod
    def get_computed_fields(cls, delimiter=", "):
        """
        Get a dict of computed fields.
        """
        return {
            "creator_approved_domains_count": cls.get_creator_approved_domains_count_query(),
            "creator_active_requests_count": cls.get_creator_active_requests_count_query(),
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

    @classmethod
    def get_related_table_fields(cls):
        """
        Get a list of fields from related tables.
        """
        return [
            "requested_domain__name",
            "federal_agency__agency",
            "senior_official__first_name",
            "senior_official__last_name",
            "senior_official__email",
            "senior_official__title",
            "creator__first_name",
            "creator__last_name",
            "creator__email",
            "investigator__email",
        ]

    # ============================================================= #
    # Helper functions for django ORM queries.                      #
    # We are using these rather than pure python for speed reasons. #
    # ============================================================= #

    @classmethod
    def get_creator_approved_domains_count_query(cls):
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

    @classmethod
    def get_creator_active_requests_count_query(cls):
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
