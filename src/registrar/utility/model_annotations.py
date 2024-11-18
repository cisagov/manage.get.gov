"""
Model annotation classes. Intended to return django querysets with computed fields for api endpoints and our csv reports.

Created to manage the complexity of the MembersTable and Members CSV report, as they require complex but common annotations.

These classes provide consistent, reusable query transformations that:
1. Add computed fields via annotations
2. Handle related model data
3. Format fields for display
4. Standardize field names across different contexts

Used by both API endpoints (e.g. portfolio members JSON) and data exports (e.g. CSV reports).

Example:
    # For a JSON table endpoint
    permissions = UserPortfolioPermissionAnnotation.get_annotated_queryset(portfolio)
    # Returns queryset with standardized fields for member tables
    
    # For a CSV export
    permissions = UserPortfolioPermissionAnnotation.get_annotated_queryset(portfolio, csv_report=True)
    # Returns same fields but formatted for CSV export
"""

from abc import ABC, abstractmethod
from registrar.models import (
    DomainInvitation,
    PortfolioInvitation,
)
from django.db.models import (
    CharField,
    F,
    ManyToManyField,
    Q,
    QuerySet,
    Value,
    TextField,
    OuterRef,
    Subquery,
    Func,
    Case,
    When,
    Exists,
)
from django.db.models.functions import Concat, Coalesce, Cast
from registrar.models.user_group import UserGroup
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.generic_helper import convert_queryset_to_dict
from registrar.models.utility.orm_helper import ArrayRemove
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.admin.models import LogEntry, ADDITION
from django.contrib.contenttypes.models import ContentType


class BaseModelAnnotation(ABC):
    """
    Abstract base class that standardizes how models are annotated for csv exports or complex annotation queries.
    For example, the Members table / csv export.

    Subclasses define model-specific annotations, filters, and field formatting while inheriting
    common queryset building logic.
    Intended ensure consistent data presentation across both table UI components and CSV exports.
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
    def get_filter_conditions(cls, **kwargs):
        """
        Get a Q object of filter conditions to filter when building queryset.
        """
        return Q()

    @classmethod
    def get_annotated_fields(cls, **kwargs):
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
    def annotate_and_retrieve_fields(
        cls, initial_queryset, annotated_fields, related_table_fields=None, include_many_to_many=False, **kwargs
    ) -> QuerySet:
        """
        Applies annotations to a queryset and retrieves specified fields,
        including class-defined and annotation-defined.

        Parameters:
            initial_queryset (QuerySet): Initial queryset.
            annotated_fields (dict, optional): Fields to compute {field_name: expression}.
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
        if annotated_fields:
            related_table_fields.extend(annotated_fields.keys())

        # Get prexisting fields on the model
        model_fields = set()
        for field in cls.model()._meta.get_fields():
            # Exclude many to many fields unless we specify
            many_to_many = isinstance(field, ManyToManyField) and include_many_to_many
            if many_to_many or not isinstance(field, ManyToManyField):
                model_fields.add(field.name)

        queryset = initial_queryset.annotate(**annotated_fields).values(*model_fields, *related_table_fields)

        return cls.update_queryset(queryset, **kwargs)

    @classmethod
    def get_annotated_queryset(cls, **kwargs):
        sort_fields = cls.get_sort_fields()
        # Get additional args and merge with incoming kwargs
        additional_args = cls.get_additional_args()
        kwargs.update(additional_args)
        select_related = cls.get_select_related()
        prefetch_related = cls.get_prefetch_related()
        exclusions = cls.get_exclusions()
        annotations_for_sort = cls.get_annotations_for_sort()
        filter_conditions = cls.get_filter_conditions(**kwargs)
        annotated_fields = cls.get_annotated_fields(**kwargs)
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
        return cls.annotate_and_retrieve_fields(model_queryset, annotated_fields, related_table_fields, **kwargs)

    @classmethod
    def update_queryset(cls, queryset, **kwargs):
        """
        Returns an updated queryset. Override in subclass to update queryset.
        """
        return queryset

    @classmethod
    def get_model_annotation_dict(cls, **kwargs):
        return convert_queryset_to_dict(cls.get_annotated_queryset(**kwargs), is_model=False)


class UserPortfolioPermissionModelAnnotation(BaseModelAnnotation):
    """
    Annotates UserPortfolioPermission querysets with computed fields for member tables.
    Handles formatting of user details, permissions, and related domain information
    for both UI display and CSV export.
    """

    @classmethod
    def model(cls):
        # Return the model class that this export handles
        return UserPortfolioPermission

    @classmethod
    def get_select_related(cls):
        """
        Get a list of tables to pass to select_related when building queryset.
        """
        return ["user"]

    @classmethod
    def get_filter_conditions(cls, portfolio, **kwargs):
        """
        Get a Q object of filter conditions to filter when building queryset.
        """
        if not portfolio:
            # Return nothing
            return Q(id__in=[])

        # Get all members on this portfolio
        return Q(portfolio=portfolio)

    @classmethod
    def get_annotated_fields(cls, portfolio, csv_report=False):
        """
        Get a dict of computed fields. These are fields that do not exist on the model normally
        and will be passed to .annotate() when building a queryset.
        """
        if not portfolio:
            # Return nothing
            return {}

        # Tweak the queries slightly to only return the data we need.
        # When returning data for the csv report we:
        # 1. Only return the domain name for 'domain_info' rather than also add ':' seperated id
        # 2. Return a formatted date for 'last_active'
        # These are just optimizations that are better done in SQL as opposed to python.
        if csv_report:
            domain_query = F("user__permissions__domain__name")
            last_active_query = Func(
                F("user__last_login"), Value("YYYY-MM-DD"), function="to_char", output_field=TextField()
            )
        else:
            domain_query = Concat(
                F("user__permissions__domain_id"),
                Value(":"),
                F("user__permissions__domain__name"),
                output_field=CharField(),
            )
            last_active_query = Cast(F("user__last_login"), output_field=TextField())

        return {
            "first_name": F("user__first_name"),
            "last_name": F("user__last_name"),
            "email_display": F("user__email"),
            "last_active": Coalesce(
                last_active_query,
                Value("Invalid date"),
                output_field=TextField(),
            ),
            "additional_permissions_display": F("additional_permissions"),
            "member_display": Case(
                When(Q(user__email__isnull=False) & ~Q(user__email=""), then=F("user__email")),
                When(
                    Q(user__first_name__isnull=False) | Q(user__last_name__isnull=False),
                    then=Concat(
                        Coalesce(F("user__first_name"), Value("")),
                        Value(" "),
                        Coalesce(F("user__last_name"), Value("")),
                    ),
                ),
                default=Value(""),
                output_field=CharField(),
            ),
            "domain_info": ArrayAgg(
                domain_query,
                distinct=True,
                filter=Q(user__permissions__domain__isnull=False)
                & Q(user__permissions__domain__domain_info__portfolio=portfolio),
            ),
            "source": Value("permission", output_field=CharField()),
            "invitation_date": Coalesce(
                Func(F("invitation__created_at"), Value("YYYY-MM-DD"), function="to_char", output_field=TextField()),
                Value("Invalid date"),
                output_field=TextField(),
            ),
            "invited_by": PortfolioInvitationModelAnnotation.get_invited_by_from_audit_log_query(
                object_id_query=Cast(OuterRef("invitation__id"), output_field=TextField())
            ),
        }

    @classmethod
    def get_annotated_queryset(cls, portfolio, csv_report=False):
        """Override of the base annotated queryset to pass in portfolio"""
        return super().get_annotated_queryset(portfolio=portfolio, csv_report=csv_report)


class PortfolioInvitationModelAnnotation(BaseModelAnnotation):
    """
    Annotates PortfolioInvitation querysets with computed fields for the member table.
    Handles formatting of user details, permissions, and related domain information
    for both UI display and CSV export.
    """

    @classmethod
    def model(cls):
        # Return the model class that this export handles
        return PortfolioInvitation

    @classmethod
    def get_exclusions(cls):
        """
        Get a Q object of exclusion conditions to pass to .exclude() when building queryset.
        """
        return Q(status=PortfolioInvitation.PortfolioInvitationStatus.RETRIEVED)

    @classmethod
    def get_filter_conditions(cls, portfolio, **kwargs):
        """
        Get a Q object of filter conditions to filter when building queryset.
        """
        if not portfolio:
            # Return nothing
            return Q(id__in=[])

        # Get all members on this portfolio
        return Q(portfolio=portfolio)

    @classmethod
    def get_invited_by_from_audit_log_query(cls, object_id_query):
        return Coalesce(
            Subquery(
                LogEntry.objects.filter(
                    content_type=ContentType.objects.get_for_model(PortfolioInvitation),
                    object_id=object_id_query,
                    action_flag=ADDITION,
                )
                .annotate(
                    display_email=Case(
                        When(
                            Exists(
                                UserGroup.objects.filter(
                                    name__in=["cisa_analysts_group", "full_access_group"],
                                    user=OuterRef("user"),
                                )
                            ),
                            then=Value("help@get.gov")
                        ),
                        default=F("user__email"),
                        output_field=CharField()
                    )
                )
                .order_by("action_time")
                .values("display_email")
            ),
            Value("Unknown"),
            output_field=CharField(),
        )

    @classmethod
    def get_annotated_fields(cls, portfolio, csv_report=False):
        """
        Get a dict of computed fields. These are fields that do not exist on the model normally
        and will be passed to .annotate() when building a queryset.
        """
        if not portfolio:
            # Return nothing
            return {}

        # Tweak the queries slightly to only return the data we need
        if csv_report:
            domain_query = F("domain__name")
        else:
            domain_query = Concat(F("domain__id"), Value(":"), F("domain__name"), output_field=CharField())

        # Get all existing domain invitations and search on that for domains the user exists on
        domain_invitations = DomainInvitation.objects.filter(
            email=OuterRef("email"),  # Check if email matches the OuterRef("email")
            domain__domain_info__portfolio=portfolio,  # Check if the domain's portfolio matches the given portfolio
        ).annotate(domain_info=domain_query)
        return {
            "first_name": Value(None, output_field=CharField()),
            "last_name": Value(None, output_field=CharField()),
            "email_display": F("email"),
            "last_active": Value("Invited", output_field=TextField()),
            "additional_permissions_display": F("additional_permissions"),
            "member_display": F("email"),
            "domain_info": ArrayRemove(
                ArrayAgg(
                    Subquery(domain_invitations.values("domain_info")),
                    distinct=True,
                )
            ),
            "source": Value("invitation", output_field=CharField()),
            "invitation_date": Coalesce(
                Func(F("created_at"), Value("YYYY-MM-DD"), function="to_char", output_field=TextField()),
                Value("Invalid date"),
                output_field=TextField(),
            ),
            # TODO - replace this with a "creator" field on portfolio invitation. This should be another ticket.
            # Grab the invitation creator from the audit log. This will need to be replaced with a creator field.
            # When that happens, just replace this with F("invitation__creator")
            "invited_by": cls.get_invited_by_from_audit_log_query(
                object_id_query=Cast(OuterRef("id"), output_field=TextField())
            ),
        }

    @classmethod
    def get_annotated_queryset(cls, portfolio, csv_report=False):
        """Override of the base annotated queryset to pass in portfolio"""
        return super().get_annotated_queryset(portfolio=portfolio, csv_report=csv_report)
