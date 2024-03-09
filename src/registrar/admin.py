from datetime import date
import logging

from django import forms
from django.db.models.functions import Concat, Coalesce
from django.db.models import Value, CharField, Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django_fsm import get_available_FIELD_transitions
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from dateutil.relativedelta import relativedelta  # type: ignore
from epplibwrapper.errors import ErrorCode, RegistryError
from registrar.models import Contact, Domain, DomainRequest, DraftDomain, User, Website
from registrar.utility import csv_export
from registrar.views.utility.mixins import OrderableFieldsMixin
from django.contrib.admin.views.main import ORDER_VAR
from registrar.widgets import NoAutocompleteFilteredSelectMultiple
from . import models
from auditlog.models import LogEntry  # type: ignore
from auditlog.admin import LogEntryAdmin  # type: ignore
from django_fsm import TransitionNotAllowed  # type: ignore
from django.utils.safestring import mark_safe
from django.utils.html import escape
from django.contrib.auth.forms import UserChangeForm, UsernameField

from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class MyUserAdminForm(UserChangeForm):
    """This form utilizes the custom widget for its class's ManyToMany UIs.

    It inherits from UserChangeForm which has special handling for the password and username fields."""

    class Meta:
        model = models.User
        fields = "__all__"
        field_classes = {"username": UsernameField}
        widgets = {
            "groups": NoAutocompleteFilteredSelectMultiple("groups", False),
            "user_permissions": NoAutocompleteFilteredSelectMultiple("user_permissions", False),
        }


class DomainInformationAdminForm(forms.ModelForm):
    """This form utilizes the custom widget for its class's ManyToMany UIs."""

    class Meta:
        model = models.DomainInformation
        fields = "__all__"
        widgets = {
            "other_contacts": NoAutocompleteFilteredSelectMultiple("other_contacts", False),
        }


class DomainInformationInlineForm(forms.ModelForm):
    """This form utilizes the custom widget for its class's ManyToMany UIs."""

    class Meta:
        model = models.DomainInformation
        fields = "__all__"
        widgets = {
            "other_contacts": NoAutocompleteFilteredSelectMultiple("other_contacts", False),
        }


class DomainRequestAdminForm(forms.ModelForm):
    """Custom form to limit transitions to available transitions.
    This form utilizes the custom widget for its class's ManyToMany UIs."""

    class Meta:
        model = models.DomainRequest
        fields = "__all__"
        widgets = {
            "current_websites": NoAutocompleteFilteredSelectMultiple("current_websites", False),
            "alternative_domains": NoAutocompleteFilteredSelectMultiple("alternative_domains", False),
            "other_contacts": NoAutocompleteFilteredSelectMultiple("other_contacts", False),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        domain_request = kwargs.get("instance")
        if domain_request and domain_request.pk:
            current_state = domain_request.status

            # first option in status transitions is current state
            available_transitions = [(current_state, domain_request.get_status_display())]

            transitions = get_available_FIELD_transitions(
                domain_request, models.DomainRequest._meta.get_field("status")
            )

            for transition in transitions:
                available_transitions.append((transition.target, transition.target.label))

            # only set the available transitions if the user is not restricted
            # from editing the domain request; otherwise, the form will be
            # readonly and the status field will not have a widget
            if not domain_request.creator.is_restricted():
                self.fields["status"].widget.choices = available_transitions


# Based off of this excellent example: https://djangosnippets.org/snippets/10471/
class MultiFieldSortableChangeList(admin.views.main.ChangeList):
    """
    This class overrides the behavior of column sorting in django admin tables in order
    to allow for multi field sorting on admin_order_field


    Usage:

    class MyCustomAdmin(admin.ModelAdmin):

        ...

        def get_changelist(self, request, **kwargs):
            return MultiFieldSortableChangeList

        ...

    """

    def get_ordering(self, request, queryset):
        """
        Returns the list of ordering fields for the change list.

        Mostly identical to the base implementation, except that now it can return
        a list of order_field objects rather than just one.
        """
        params = self.params
        ordering = list(self.model_admin.get_ordering(request) or self._get_default_ordering())

        if ORDER_VAR in params:
            # Clear ordering and used params
            ordering = []

            order_params = params[ORDER_VAR].split(".")
            for p in order_params:
                try:
                    none, pfx, idx = p.rpartition("-")
                    field_name = self.list_display[int(idx)]

                    order_fields = self.get_ordering_field(field_name)

                    if isinstance(order_fields, list):
                        for order_field in order_fields:
                            if order_field:
                                ordering.append(pfx + order_field)
                    else:
                        ordering.append(pfx + order_fields)

                except (IndexError, ValueError):
                    continue  # Invalid ordering specified, skip it.

        # Add the given query's ordering fields, if any.
        ordering.extend(queryset.query.order_by)

        # Ensure that the primary key is systematically present in the list of
        # ordering fields so we can guarantee a deterministic order across all
        # database backends.
        pk_name = self.lookup_opts.pk.name
        if not (set(ordering) & set(["pk", "-pk", pk_name, "-" + pk_name])):
            # The two sets do not intersect, meaning the pk isn't present. So
            # we add it.
            ordering.append("-pk")

        return ordering


class CustomLogEntryAdmin(LogEntryAdmin):
    """Overwrite the generated LogEntry admin class"""

    list_display = [
        "created",
        "resource",
        "action",
        "msg_short",
        "user_url",
    ]

    # We name the custom prop 'resource' because linter
    # is not allowing a short_description attr on it
    # This gets around the linter limitation, for now.
    def resource(self, obj):
        # Return the field value without a link
        return f"{obj.content_type} - {obj.object_repr}"

    search_help_text = "Search by resource, changes, or user."

    change_form_template = "admin/change_form_no_submit.html"
    add_form_template = "admin/change_form_no_submit.html"


class AdminSortFields:
    _name_sort = ["first_name", "last_name", "email"]

    # Define a mapping of field names to model querysets and sort expressions.
    # A dictionary is used for specificity, but the downside is some degree of repetition.
    # To eliminate this, this list can be generated dynamically but the readability of that
    # is impacted.
    sort_mapping = {
        # == Contact == #
        "other_contacts": (Contact, _name_sort),
        "authorizing_official": (Contact, _name_sort),
        "submitter": (Contact, _name_sort),
        # == User == #
        "creator": (User, _name_sort),
        "user": (User, _name_sort),
        "investigator": (User, _name_sort),
        # == Website == #
        "current_websites": (Website, "website"),
        "alternative_domains": (Website, "website"),
        # == DraftDomain == #
        "requested_domain": (DraftDomain, "name"),
        # == DomainRequest == #
        "domain_request": (DomainRequest, "requested_domain__name"),
        # == Domain == #
        "domain": (Domain, "name"),
        "approved_domain": (Domain, "name"),
    }

    @classmethod
    def get_queryset(cls, db_field):
        """This is a helper function for formfield_for_manytomany and formfield_for_foreignkey"""
        queryset_info = cls.sort_mapping.get(db_field.name, None)
        if queryset_info is None:
            return None

        # Grab the model we want to order, and grab how we want to order it
        model, order_by = queryset_info
        match db_field.name:
            case "investigator":
                # We should only return users who are staff.
                return model.objects.filter(is_staff=True).order_by(*order_by)
            case _:
                if isinstance(order_by, list) or isinstance(order_by, tuple):
                    return model.objects.order_by(*order_by)
                else:
                    return model.objects.order_by(order_by)


class AuditedAdmin(admin.ModelAdmin):
    """Custom admin to make auditing easier."""

    def history_view(self, request, object_id, extra_context=None):
        """On clicking 'History', take admin to the auditlog view for an object."""
        return HttpResponseRedirect(
            "{url}?resource_type={content_type}&object_id={object_id}".format(
                url=reverse("admin:auditlog_logentry_changelist", args=()),
                content_type=ContentType.objects.get_for_model(self.model).pk,
                object_id=object_id,
            )
        )

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """customize the behavior of formfields with manytomany relationships.  the customized
        behavior includes sorting of objects in lists as well as customizing helper text"""

        # Define a queryset. Note that in the super of this,
        # a new queryset will only be generated if one does not exist.
        # Thus, the order in which we define queryset matters.
        queryset = AdminSortFields.get_queryset(db_field)
        if queryset:
            kwargs["queryset"] = queryset

        formfield = super().formfield_for_manytomany(db_field, request, **kwargs)
        # customize the help text for all formfields for manytomany
        formfield.help_text = (
            formfield.help_text
            + " If more than one value is selected, the change/delete/view actions will be disabled."
        )
        return formfield

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Customize the behavior of formfields with foreign key relationships. This will customize
        the behavior of selects. Customized behavior includes sorting of objects in list."""

        # Define a queryset. Note that in the super of this,
        # a new queryset will only be generated if one does not exist.
        # Thus, the order in which we define queryset matters.
        queryset = AdminSortFields.get_queryset(db_field)
        if queryset:
            kwargs["queryset"] = queryset

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class ListHeaderAdmin(AuditedAdmin, OrderableFieldsMixin):
    """Custom admin to add a descriptive subheader to list views
    and custom table sort behaviour"""

    def get_changelist(self, request, **kwargs):
        """Returns a custom ChangeList class, as opposed to the default.
        This is so we can override the behaviour of the `admin_order_field` field.
        By default, django does not support ordering by multiple fields for this
        particular field (i.e. self.admin_order_field=["first_name", "last_name"] is invalid).

        Reference: https://code.djangoproject.com/ticket/31975
        """
        return MultiFieldSortableChangeList

    def changelist_view(self, request, extra_context=None):
        if extra_context is None:
            extra_context = {}
        # Get the filtered values
        filters = self.get_filters(request)
        # Pass the filtered values to the template context
        extra_context["filters"] = filters
        extra_context["search_query"] = request.GET.get("q", "")  # Assuming the search query parameter is 'q'
        return super().changelist_view(request, extra_context=extra_context)

    def get_filters(self, request):
        """Retrieve the current set of parameters being used to filter the table
        Returns:
            dictionary objects in the format {parameter_name: string,
            parameter_value: string}
        TODO: convert investigator id to investigator username
        """
        filters = []
        # Retrieve the filter parameters
        for param in request.GET.keys():
            # Exclude the default search parameter 'q'
            if param != "q" and param != "o":
                parameter_name = param.replace("__exact", "").replace("_type", "").replace("__id", " id")

                if parameter_name == "investigator id":
                    # Retrieves the corresponding contact from Users
                    id_value = request.GET.get(param)
                    try:
                        contact = models.User.objects.get(id=id_value)
                        investigator_name = contact.first_name + " " + contact.last_name

                        filters.append(
                            {
                                "parameter_name": "investigator",
                                "parameter_value": investigator_name,
                            }
                        )
                    except models.User.DoesNotExist:
                        pass
                else:
                    # For other parameter names, append a dictionary with the original
                    # parameter_name and the corresponding parameter_value
                    filters.append(
                        {
                            "parameter_name": parameter_name,
                            "parameter_value": request.GET.get(param),
                        }
                    )
        return filters


class UserContactInline(admin.StackedInline):
    """Edit a user's profile on the user page."""

    model = models.Contact


class MyUserAdmin(BaseUserAdmin):
    """Custom user admin class to use our inlines."""

    form = MyUserAdminForm

    class Meta:
        """Contains meta information about this class"""

        model = models.User
        fields = "__all__"

    _meta = Meta()

    inlines = [UserContactInline]

    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        # Group is a custom property defined within this file,
        # rather than in a model like the other properties
        "group",
        "status",
    )

    fieldsets = (
        (
            None,
            {"fields": ("username", "password", "status")},
        ),
        ("Personal Info", {"fields": ("first_name", "last_name", "email")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    # Hide Username (uuid), Groups and Permissions
    # Q: Now that we're using Groups and Permissions,
    # do we expose those to analysts to view?
    analyst_fieldsets = (
        (
            None,
            {"fields": ("password", "status")},
        ),
        ("Personal Info", {"fields": ("first_name", "last_name", "email")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "groups",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    analyst_list_display = [
        "email",
        "first_name",
        "last_name",
        "group",
        "status",
    ]

    # NOT all fields are readonly for admin, otherwise we would have
    # set this at the permissions level. The exception is 'status'
    analyst_readonly_fields = [
        "password",
        "Personal Info",
        "first_name",
        "last_name",
        "email",
        "Permissions",
        "is_active",
        "groups",
        "Important dates",
        "last_login",
        "date_joined",
    ]

    list_filter = (
        "is_active",
        "groups",
    )

    # this ordering effects the ordering of results
    # in autocomplete_fields for user
    ordering = ["first_name", "last_name", "email"]

    def get_search_results(self, request, queryset, search_term):
        """
        Override for get_search_results. This affects any upstream model using autocomplete_fields,
        such as DomainRequest. This is because autocomplete_fields uses an API call to fetch data,
        and this fetch comes from this method.
        """
        # Custom filtering logic
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)

        # If we aren't given a request to modify, we shouldn't try to
        if request is None or not hasattr(request, "GET"):
            return queryset, use_distinct

        # Otherwise, lets modify it!
        request_get = request.GET

        # The request defines model name and field name.
        # For instance, model_name could be "DomainRequest"
        # and field_name could be "investigator".
        model_name = request_get.get("model_name", None)
        field_name = request_get.get("field_name", None)

        # Make sure we're only modifying requests from these models.
        models_to_target = {"domainrequest"}
        if model_name in models_to_target:
            # Define rules per field
            match field_name:
                case "investigator":
                    # We should not display investigators who don't have a staff role
                    queryset = queryset.filter(is_staff=True)
                case _:
                    # In the default case, do nothing
                    pass

        return queryset, use_distinct

    # Let's define First group
    # (which should in theory be the ONLY group)
    def group(self, obj):
        if obj.groups.filter(name="full_access_group").exists():
            return "full_access_group"
        elif obj.groups.filter(name="cisa_analysts_group").exists():
            return "cisa_analysts_group"
        return ""

    def get_list_display(self, request):
        # The full_access_permission perm will load onto the full_access_group
        # which is equivalent to superuser. The other group we use to manage
        # perms is cisa_analysts_group. cisa_analysts_group will never contain
        # full_access_permission
        if request.user.has_perm("registrar.full_access_permission"):
            # Use the default list display for all access users
            return super().get_list_display(request)

        # Customize the list display for analysts
        return self.analyst_list_display

    def get_fieldsets(self, request, obj=None):
        if request.user.has_perm("registrar.full_access_permission"):
            # Show all fields for all access users
            return super().get_fieldsets(request, obj)
        elif request.user.has_perm("registrar.analyst_access_permission"):
            # show analyst_fieldsets for analysts
            return self.analyst_fieldsets
        else:
            # any admin user should belong to either full_access_group
            # or cisa_analyst_group
            return []

    def get_readonly_fields(self, request, obj=None):
        if request.user.has_perm("registrar.full_access_permission"):
            return ()  # No read-only fields for all access users
        # Return restrictive Read-only fields for analysts and
        # users who might not belong to groups
        return self.analyst_readonly_fields


class HostIPInline(admin.StackedInline):
    """Edit an ip address on the host page."""

    model = models.HostIP


class MyHostAdmin(AuditedAdmin):
    """Custom host admin class to use our inlines."""

    search_fields = ["name", "domain__name"]
    search_help_text = "Search by domain or hostname."
    inlines = [HostIPInline]


class ContactAdmin(ListHeaderAdmin):
    """Custom contact admin class to add search."""

    search_fields = ["email", "first_name", "last_name"]
    search_help_text = "Search by firstname, lastname or email."
    list_display = [
        "contact",
        "email",
    ]
    # this ordering effects the ordering of results
    # in autocomplete_fields for user
    ordering = ["first_name", "last_name", "email"]

    # We name the custom prop 'contact' because linter
    # is not allowing a short_description attr on it
    # This gets around the linter limitation, for now.
    def contact(self, obj: models.Contact):
        """Duplicate the contact _str_"""
        if obj.first_name or obj.last_name:
            return obj.get_formatted_name()
        elif obj.email:
            return obj.email
        elif obj.pk:
            return str(obj.pk)
        else:
            return ""

    contact.admin_order_field = "first_name"  # type: ignore

    # Read only that we'll leverage for CISA Analysts
    analyst_readonly_fields = [
        "user",
    ]

    def get_readonly_fields(self, request, obj=None):
        """Set the read-only state on form elements.
        We have 1 conditions that determine which fields are read-only:
        admin user permissions.
        """

        readonly_fields = list(self.readonly_fields)

        if request.user.has_perm("registrar.full_access_permission"):
            return readonly_fields
        # Return restrictive Read-only fields for analysts and
        # users who might not belong to groups
        readonly_fields.extend([field for field in self.analyst_readonly_fields])
        return readonly_fields  # Read-only fields for analysts

    def change_view(self, request, object_id, form_url="", extra_context=None):
        """Extend the change_view for Contact objects in django admin.
        Customize to display related objects to the Contact. These will be passed
        through the messages construct to the template for display to the user."""

        # Fetch the Contact instance
        contact = models.Contact.objects.get(pk=object_id)

        # initialize related_objects array
        related_objects = []
        # for all defined fields in the model
        for related_field in contact._meta.get_fields():
            # if the field is a relation to another object
            if related_field.is_relation:
                # Check if the related field is not None
                related_manager = getattr(contact, related_field.name)
                if related_manager is not None:
                    # Check if it's a ManyToManyField/reverse ForeignKey or a OneToOneField
                    # Do this by checking for get_queryset method on the related_manager
                    if hasattr(related_manager, "get_queryset"):
                        # Handles ManyToManyRel and ManyToOneRel
                        queryset = related_manager.get_queryset()
                    else:
                        # Handles OneToOne rels, ie. User
                        queryset = [related_manager]

                    for obj in queryset:
                        # for each object, build the edit url in this view and add as tuple
                        # to the related_objects array
                        app_label = obj._meta.app_label
                        model_name = obj._meta.model_name
                        obj_id = obj.id
                        change_url = reverse("admin:%s_%s_change" % (app_label, model_name), args=[obj_id])
                        related_objects.append((change_url, obj))

        if related_objects:
            message = "<ul class='messagelist_content-list--unstyled'>"
            for i, (url, obj) in enumerate(related_objects):
                if i < 5:
                    escaped_obj = escape(obj)
                    message += f"<li>Joined to {obj.__class__.__name__}: <a href='{url}'>{escaped_obj}</a></li>"
            message += "</ul>"
            if len(related_objects) > 5:
                related_objects_over_five = len(related_objects) - 5
                message += f"<p class='font-sans-3xs'>And {related_objects_over_five} more...</p>"

            message_html = mark_safe(message)  # nosec
            messages.warning(
                request,
                message_html,
            )

        return super().change_view(request, object_id, form_url, extra_context=extra_context)


class WebsiteAdmin(ListHeaderAdmin):
    """Custom website admin class."""

    # Search
    search_fields = [
        "website",
    ]
    search_help_text = "Search by website."


class UserDomainRoleAdmin(ListHeaderAdmin):
    """Custom user domain role admin class."""

    class Meta:
        """Contains meta information about this class"""

        model = models.UserDomainRole
        fields = "__all__"

    _meta = Meta()

    # Columns
    list_display = [
        "user",
        "domain",
        "role",
    ]

    orderable_fk_fields = [
        ("domain", "name"),
        ("user", ["first_name", "last_name", "email"]),
    ]

    # Search
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__email",
        "domain__name",
        "role",
    ]
    search_help_text = "Search by firstname, lastname, email, domain, or role."

    autocomplete_fields = ["user", "domain"]

    # Fixes a bug where non-superusers are redirected to the main page
    def delete_view(self, request, object_id, extra_context=None):
        """Custom delete_view implementation that specifies redirect behaviour"""
        response = super().delete_view(request, object_id, extra_context)

        if isinstance(response, HttpResponseRedirect) and not request.user.has_perm("registrar.full_access_permission"):
            url = reverse("admin:registrar_userdomainrole_changelist")
            return redirect(url)
        else:
            return response


class DomainInvitationAdmin(ListHeaderAdmin):
    """Custom domain invitation admin class."""

    class Meta:
        model = models.DomainInvitation
        fields = "__all__"

    _meta = Meta()

    # Columns
    list_display = [
        "email",
        "domain",
        "status",
    ]

    # Search
    search_fields = [
        "email",
        "domain__name",
    ]

    # Filters
    list_filter = ("status",)

    search_help_text = "Search by email or domain."

    # Mark the FSM field 'status' as readonly
    # to allow admin users to create Domain Invitations
    # without triggering the FSM Transition Not Allowed
    # error.
    readonly_fields = ["status"]


class DomainInformationAdmin(ListHeaderAdmin):
    """Customize domain information admin class."""

    form = DomainInformationAdminForm

    # Columns
    list_display = [
        "domain",
        "organization_type",
        "created_at",
        "submitter",
    ]

    orderable_fk_fields = [
        ("domain", "name"),
        ("submitter", ["first_name", "last_name"]),
    ]

    # Filters
    list_filter = ["organization_type"]

    # Search
    search_fields = [
        "domain__name",
    ]
    search_help_text = "Search by domain."

    fieldsets = [
        (None, {"fields": ["creator", "submitter", "domain_request", "notes"]}),
        (".gov domain", {"fields": ["domain"]}),
        ("Contacts", {"fields": ["authorizing_official", "other_contacts", "no_other_contacts_rationale"]}),
        ("Background info", {"fields": ["anything_else"]}),
        (
            "Type of organization",
            {
                "fields": [
                    "organization_type",
                    "is_election_board",
                    "federal_type",
                    "federal_agency",
                    "tribe_name",
                    "federally_recognized_tribe",
                    "state_recognized_tribe",
                    "about_your_organization",
                ]
            },
        ),
        (
            "Organization name and mailing address",
            {
                "fields": [
                    "organization_name",
                    "state_territory",
                    "address_line1",
                    "address_line2",
                    "city",
                    "zipcode",
                    "urbanization",
                ]
            },
        ),
    ]

    # Read only that we'll leverage for CISA Analysts
    analyst_readonly_fields = [
        "creator",
        "type_of_work",
        "more_organization_information",
        "domain",
        "domain_request",
        "submitter",
        "no_other_contacts_rationale",
        "anything_else",
        "is_policy_acknowledged",
    ]

    # For each filter_horizontal, init in admin js extendFilterHorizontalWidgets
    # to activate the edit/delete/view buttons
    filter_horizontal = ("other_contacts",)

    autocomplete_fields = [
        "creator",
        "domain_request",
        "authorizing_official",
        "domain",
        "submitter",
    ]

    # Table ordering
    ordering = ["domain__name"]

    def get_readonly_fields(self, request, obj=None):
        """Set the read-only state on form elements.
        We have 1 conditions that determine which fields are read-only:
        admin user permissions.
        """

        readonly_fields = list(self.readonly_fields)

        if request.user.has_perm("registrar.full_access_permission"):
            return readonly_fields
        # Return restrictive Read-only fields for analysts and
        # users who might not belong to groups
        readonly_fields.extend([field for field in self.analyst_readonly_fields])
        return readonly_fields  # Read-only fields for analysts


class DomainRequestAdmin(ListHeaderAdmin):
    """Custom domain requests admin class."""

    form = DomainRequestAdminForm

    class InvestigatorFilter(admin.SimpleListFilter):
        """Custom investigator filter that only displays users with the manager role"""

        title = "investigator"
        # Match the old param name to avoid unnecessary refactoring
        parameter_name = "investigator__id__exact"

        def lookups(self, request, model_admin):
            """Lookup reimplementation, gets users of is_staff.
            Returns a list of tuples consisting of (user.id, user)
            """
            # Select all investigators that are staff, then order by name and email
            privileged_users = (
                DomainRequest.objects.select_related("investigator")
                .filter(investigator__is_staff=True)
                .order_by("investigator__first_name", "investigator__last_name", "investigator__email")
            )

            # Annotate the full name and return a values list that lookups can use
            privileged_users_annotated = (
                privileged_users.annotate(
                    full_name=Coalesce(
                        Concat(
                            "investigator__first_name", Value(" "), "investigator__last_name", output_field=CharField()
                        ),
                        "investigator__email",
                        output_field=CharField(),
                    )
                )
                .values_list("investigator__id", "full_name")
                .distinct()
            )

            return privileged_users_annotated

        def queryset(self, request, queryset):
            """Custom queryset implementation, filters by investigator"""
            if self.value() is None:
                return queryset
            else:
                return queryset.filter(investigator__id__exact=self.value())

    class ElectionOfficeFilter(admin.SimpleListFilter):
        """Define a custom filter for is_election_board"""

        title = _("election office")
        parameter_name = "is_election_board"

        def lookups(self, request, model_admin):
            return (
                ("1", _("Yes")),
                ("0", _("No")),
            )

        def queryset(self, request, queryset):
            if self.value() == "1":
                return queryset.filter(is_election_board=True)
            if self.value() == "0":
                return queryset.filter(Q(is_election_board=False) | Q(is_election_board=None))

    # Columns
    list_display = [
        "requested_domain",
        "status",
        "organization_type",
        "federal_type",
        "federal_agency",
        "organization_name",
        "custom_election_board",
        "city",
        "state_territory",
        "created_at",
        "submitter",
        "investigator",
    ]

    orderable_fk_fields = [
        ("requested_domain", "name"),
        ("submitter", ["first_name", "last_name"]),
        ("investigator", ["first_name", "last_name"]),
    ]

    def custom_election_board(self, obj):
        return "Yes" if obj.is_election_board else "No"

    custom_election_board.admin_order_field = "is_election_board"  # type: ignore
    custom_election_board.short_description = "Election office"  # type: ignore

    # Filters
    list_filter = (
        "status",
        "organization_type",
        "federal_type",
        ElectionOfficeFilter,
        "rejection_reason",
        InvestigatorFilter,
    )

    # Search
    search_fields = [
        "requested_domain__name",
        "submitter__email",
        "submitter__first_name",
        "submitter__last_name",
    ]
    search_help_text = "Search by domain or submitter."

    fieldsets = [
        (None, {"fields": ["status", "rejection_reason", "investigator", "creator", "submitter", "approved_domain", "notes"]}),
        (".gov domain", {"fields": ["requested_domain", "alternative_domains"]}),
        ("Contacts", {"fields": ["authorizing_official", "other_contacts", "no_other_contacts_rationale"]}),
        ("Background info", {"fields": ["purpose", "anything_else", "current_websites"]}),
        (
            "Type of organization",
            {
                "fields": [
                    "organization_type",
                    "is_election_board",
                    "federal_type",
                    "federal_agency",
                    "tribe_name",
                    "federally_recognized_tribe",
                    "state_recognized_tribe",
                    "about_your_organization",
                ]
            },
        ),
        (
            "Organization name and mailing address",
            {
                "fields": [
                    "organization_name",
                    "state_territory",
                    "address_line1",
                    "address_line2",
                    "city",
                    "zipcode",
                    "urbanization",
                ]
            },
        ),
    ]

    # Read only that we'll leverage for CISA Analysts
    analyst_readonly_fields = [
        "creator",
        "about_your_organization",
        "requested_domain",
        "approved_domain",
        "alternative_domains",
        "purpose",
        "submitter",
        "no_other_contacts_rationale",
        "anything_else",
        "is_policy_acknowledged",
    ]
    autocomplete_fields = [
        "approved_domain",
        "requested_domain",
        "submitter",
        "creator",
        "authorizing_official",
        "investigator",
    ]
    filter_horizontal = ("current_websites", "alternative_domains", "other_contacts")

    # Table ordering
    ordering = ["requested_domain__name"]

    # Trigger action when a fieldset is changed
    def save_model(self, request, obj, form, change):
        if obj and obj.creator.status != models.User.RESTRICTED:
            if change:  # Check if the domain request is being edited
                # Get the original domain request from the database
                original_obj = models.DomainRequest.objects.get(pk=obj.pk)

                if (
                    obj
                    and original_obj.status == models.DomainRequest.DomainRequestStatus.APPROVED
                    and obj.status != models.DomainRequest.DomainRequestStatus.APPROVED
                    and not obj.domain_is_not_active()
                ):
                    # If an admin tried to set an approved domain request to
                    # another status and the related domain is already
                    # active, shortcut the action and throw a friendly
                    # error message. This action would still not go through
                    # shortcut or not as the rules are duplicated on the model,
                    # but the error would be an ugly Django error screen.

                    # Clear the success message
                    messages.set_level(request, messages.ERROR)

                    messages.error(
                        request,
                        "This action is not permitted. The domain is already active.",
                    )

                elif (
                    obj and obj.status == models.DomainRequest.DomainRequestStatus.REJECTED and not obj.rejection_reason
                ):
                    # This condition should never be triggered.
                    # The opposite of this condition is acceptable (rejected -> other status and rejection_reason)
                    # because we clean up the rejection reason in the transition in the model.

                    # Clear the success message
                    messages.set_level(request, messages.ERROR)

                    messages.error(
                        request,
                        "A rejection reason is required.",
                    )

                else:
                    if obj.status != original_obj.status:
                        status_method_mapping = {
                            models.DomainRequest.DomainRequestStatus.STARTED: None,
                            models.DomainRequest.DomainRequestStatus.SUBMITTED: obj.submit,
                            models.DomainRequest.DomainRequestStatus.IN_REVIEW: obj.in_review,
                            models.DomainRequest.DomainRequestStatus.ACTION_NEEDED: obj.action_needed,
                            models.DomainRequest.DomainRequestStatus.APPROVED: obj.approve,
                            models.DomainRequest.DomainRequestStatus.WITHDRAWN: obj.withdraw,
                            models.DomainRequest.DomainRequestStatus.REJECTED: obj.reject,
                            models.DomainRequest.DomainRequestStatus.INELIGIBLE: (obj.reject_with_prejudice),
                        }
                        selected_method = status_method_mapping.get(obj.status)
                        if selected_method is None:
                            logger.warning("Unknown status selected in django admin")
                        else:
                            # This is an fsm in model which will throw an error if the
                            # transition condition is violated, so we roll back the
                            # status to what it was before the admin user changed it and
                            # let the fsm method set it.
                            obj.status = original_obj.status
                            selected_method()

                    super().save_model(request, obj, form, change)
        else:
            # Clear the success message
            messages.set_level(request, messages.ERROR)

            messages.error(
                request,
                "This action is not permitted for domain requests with a restricted creator.",
            )

    def get_readonly_fields(self, request, obj=None):
        """Set the read-only state on form elements.
        We have 2 conditions that determine which fields are read-only:
        admin user permissions and the domain request creator's status, so
        we'll use the baseline readonly_fields and extend it as needed.
        """
        readonly_fields = list(self.readonly_fields)

        # Check if the creator is restricted
        if obj and obj.creator.status == models.User.RESTRICTED:
            # For fields like CharField, IntegerField, etc., the widget used is
            # straightforward and the readonly_fields list can control their behavior
            readonly_fields.extend([field.name for field in self.model._meta.fields])
            # Add the multi-select fields to readonly_fields:
            # Complex fields like ManyToManyField require special handling
            readonly_fields.extend(["current_websites", "other_contacts", "alternative_domains"])

        if request.user.has_perm("registrar.full_access_permission"):
            return readonly_fields
        # Return restrictive Read-only fields for analysts and
        # users who might not belong to groups
        readonly_fields.extend([field for field in self.analyst_readonly_fields])
        return readonly_fields

    def display_restricted_warning(self, request, obj):
        if obj and obj.creator.status == models.User.RESTRICTED:
            messages.warning(
                request,
                "Cannot edit a domain request with a restricted creator.",
            )

    def change_view(self, request, object_id, form_url="", extra_context=None):
        obj = self.get_object(request, object_id)
        self.display_restricted_warning(request, obj)
        return super().change_view(request, object_id, form_url, extra_context)


class TransitionDomainAdmin(ListHeaderAdmin):
    """Custom transition domain admin class."""

    # Columns
    list_display = [
        "username",
        "domain_name",
        "status",
        "email_sent",
        "processed",
    ]

    search_fields = ["username", "domain_name"]
    search_help_text = "Search by user or domain name."


class DomainInformationInline(admin.StackedInline):
    """Edit a domain information on the domain page.
    We had issues inheriting from both StackedInline
    and the source DomainInformationAdmin since these
    classes conflict, so we'll just pull what we need
    from DomainInformationAdmin"""

    form = DomainInformationInlineForm

    model = models.DomainInformation

    fieldsets = DomainInformationAdmin.fieldsets
    analyst_readonly_fields = DomainInformationAdmin.analyst_readonly_fields
    # For each filter_horizontal, init in admin js extendFilterHorizontalWidgets
    # to activate the edit/delete/view buttons
    filter_horizontal = ("other_contacts",)

    autocomplete_fields = [
        "creator",
        "domain_request",
        "authorizing_official",
        "domain",
        "submitter",
    ]

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """customize the behavior of formfields with manytomany relationships.  the customized
        behavior includes sorting of objects in lists as well as customizing helper text"""
        queryset = AdminSortFields.get_queryset(db_field)
        if queryset:
            kwargs["queryset"] = queryset
        formfield = super().formfield_for_manytomany(db_field, request, **kwargs)
        # customize the help text for all formfields for manytomany
        formfield.help_text = (
            formfield.help_text
            + " If more than one value is selected, the change/delete/view actions will be disabled."
        )
        return formfield

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Customize the behavior of formfields with foreign key relationships. This will customize
        the behavior of selects. Customized behavior includes sorting of objects in list."""
        queryset = AdminSortFields.get_queryset(db_field)
        if queryset:
            kwargs["queryset"] = queryset
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        return DomainInformationAdmin.get_readonly_fields(self, request, obj=None)


class DomainAdmin(ListHeaderAdmin):
    """Custom domain admin class to add extra buttons."""

    class ElectionOfficeFilter(admin.SimpleListFilter):
        """Define a custom filter for is_election_board"""

        title = _("election office")
        parameter_name = "is_election_board"

        def lookups(self, request, model_admin):
            return (
                ("1", _("Yes")),
                ("0", _("No")),
            )

        def queryset(self, request, queryset):
            logger.debug(self.value())
            if self.value() == "1":
                return queryset.filter(domain_info__is_election_board=True)
            if self.value() == "0":
                return queryset.filter(Q(domain_info__is_election_board=False) | Q(domain_info__is_election_board=None))

    inlines = [DomainInformationInline]

    # Columns
    list_display = [
        "name",
        "organization_type",
        "federal_type",
        "federal_agency",
        "organization_name",
        "custom_election_board",
        "city",
        "state_territory",
        "state",
        "expiration_date",
        "created_at",
        "first_ready",
        "deleted",
    ]

    fieldsets = (
        (
            None,
            {"fields": ["name", "state", "expiration_date", "first_ready", "deleted"]},
        ),
    )

    # this ordering effects the ordering of results
    # in autocomplete_fields for domain
    ordering = ["name"]

    def organization_type(self, obj):
        return obj.domain_info.get_organization_type_display()

    organization_type.admin_order_field = "domain_info__organization_type"  # type: ignore

    def federal_agency(self, obj):
        return obj.domain_info.federal_agency if obj.domain_info else None

    federal_agency.admin_order_field = "domain_info__federal_agency"  # type: ignore

    def federal_type(self, obj):
        return obj.domain_info.federal_type if obj.domain_info else None

    federal_type.admin_order_field = "domain_info__federal_type"  # type: ignore

    def organization_name(self, obj):
        return obj.domain_info.organization_name if obj.domain_info else None

    organization_name.admin_order_field = "domain_info__organization_name"  # type: ignore

    def custom_election_board(self, obj):
        domain_info = getattr(obj, "domain_info", None)
        if domain_info:
            return "Yes" if domain_info.is_election_board else "No"
        return "No"

    custom_election_board.admin_order_field = "domain_info__is_election_board"  # type: ignore
    custom_election_board.short_description = "Election office"  # type: ignore

    def city(self, obj):
        return obj.domain_info.city if obj.domain_info else None

    city.admin_order_field = "domain_info__city"  # type: ignore

    def state_territory(self, obj):
        return obj.domain_info.state_territory if obj.domain_info else None

    state_territory.admin_order_field = "domain_info__state_territory"  # type: ignore

    # Filters
    list_filter = ["domain_info__organization_type", "domain_info__federal_type", ElectionOfficeFilter, "state"]

    search_fields = ["name"]
    search_help_text = "Search by domain name."
    change_form_template = "django/admin/domain_change_form.html"
    change_list_template = "django/admin/domain_change_list.html"
    readonly_fields = ["state", "expiration_date", "first_ready", "deleted"]

    # Table ordering
    ordering = ["name"]

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        """Custom changeform implementation to pass in context information"""
        if extra_context is None:
            extra_context = {}

        # Pass in what the an extended expiration date would be for the expiration date modal
        if object_id is not None:
            domain = Domain.objects.get(pk=object_id)
            years_to_extend_by = self._get_calculated_years_for_exp_date(domain)

            try:
                curr_exp_date = domain.registry_expiration_date
            except KeyError:
                # No expiration date was found. Return none.
                extra_context["extended_expiration_date"] = None
                return super().changeform_view(request, object_id, form_url, extra_context)

            if curr_exp_date < date.today():
                extra_context["extended_expiration_date"] = date.today() + relativedelta(years=years_to_extend_by)
            else:
                new_date = domain.registry_expiration_date + relativedelta(years=years_to_extend_by)
                extra_context["extended_expiration_date"] = new_date
        else:
            extra_context["extended_expiration_date"] = None

        return super().changeform_view(request, object_id, form_url, extra_context)

    def export_data_type(self, request):
        # match the CSV example with all the fields
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="domains-by-type.csv"'
        csv_export.export_data_type_to_csv(response)
        return response

    def export_data_full(self, request):
        # Smaller export based on 1
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="current-full.csv"'
        csv_export.export_data_full_to_csv(response)
        return response

    def export_data_federal(self, request):
        # Federal only
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="current-federal.csv"'
        csv_export.export_data_federal_to_csv(response)
        return response

    def get_urls(self):
        from django.urls import path

        urlpatterns = super().get_urls()

        # Used to extrapolate a path name, for instance
        # name="{app_label}_{model_name}_export_data_type"
        info = self.model._meta.app_label, self.model._meta.model_name

        my_url = [
            path(
                "export_data_type/",
                self.export_data_type,
                name="%s_%s_export_data_type" % info,
            ),
            path(
                "export_data_full/",
                self.export_data_full,
                name="%s_%s_export_data_full" % info,
            ),
            path(
                "export_data_federal/",
                self.export_data_federal,
                name="%s_%s_export_data_federal" % info,
            ),
        ]

        return my_url + urlpatterns

    def response_change(self, request, obj):
        # Create dictionary of action functions
        ACTION_FUNCTIONS = {
            "_place_client_hold": self.do_place_client_hold,
            "_remove_client_hold": self.do_remove_client_hold,
            "_edit_domain": self.do_edit_domain,
            "_delete_domain": self.do_delete_domain,
            "_get_status": self.do_get_status,
            "_extend_expiration_date": self.do_extend_expiration_date,
        }

        # Check which action button was pressed and call the corresponding function
        for action, function in ACTION_FUNCTIONS.items():
            if action in request.POST:
                return function(request, obj)

        # If no matching action button is found, return the super method
        return super().response_change(request, obj)

    def do_extend_expiration_date(self, request, obj):
        """Extends a domains expiration date by one year from the current date"""

        # Make sure we're dealing with a Domain
        if not isinstance(obj, Domain):
            self.message_user(request, "Object is not of type Domain.", messages.ERROR)
            return None

        years = self._get_calculated_years_for_exp_date(obj)

        # Renew the domain.
        try:
            obj.renew_domain(length=years)
            self.message_user(
                request,
                "Successfully extended the expiration date.",
            )
        except RegistryError as err:
            if err.is_connection_error():
                error_message = "Error connecting to the registry."
            else:
                error_message = f"Error extending this domain: {err}."
            self.message_user(request, error_message, messages.ERROR)
        except KeyError:
            # In normal code flow, a keyerror can only occur when
            # fresh data can't be pulled from the registry, and thus there is no cache.
            self.message_user(
                request,
                "Error connecting to the registry. No expiration date was found.",
                messages.ERROR,
            )
        except Exception as err:
            logger.error(err, stack_info=True)
            self.message_user(request, "Could not delete: An unspecified error occured", messages.ERROR)

        return HttpResponseRedirect(".")

    def _get_calculated_years_for_exp_date(self, obj, extension_period: int = 1):
        """Given the current date, an extension period, and a registry_expiration_date
        on the domain object, calculate the number of years needed to extend the
        current expiration date by the extension period.
        """
        # Get the date we want to update to
        desired_date = self._get_current_date() + relativedelta(years=extension_period)

        # Grab the current expiration date
        try:
            exp_date = obj.registry_expiration_date
        except KeyError:
            # if no expiration date from registry, set it to today
            logger.warning("current expiration date not set; setting to today")
            exp_date = self._get_current_date()

        # If the expiration date is super old (2020, for example), we need to
        # "catch up" to the current year, so we add the difference.
        # If both years match, then lets just proceed as normal.
        calculated_exp_date = exp_date + relativedelta(years=extension_period)

        year_difference = desired_date.year - exp_date.year

        years = extension_period
        if desired_date > calculated_exp_date:
            # Max probably isn't needed here (no code flow), but it guards against negative and 0.
            # In both of those cases, we just want to extend by the extension_period.
            years = max(extension_period, year_difference)

        return years

    # Workaround for unit tests, as we cannot mock date directly.
    # it is immutable. Rather than dealing with a convoluted workaround,
    # lets wrap this in a function.
    def _get_current_date(self):
        """Gets the current date"""
        return date.today()

    def do_delete_domain(self, request, obj):
        if not isinstance(obj, Domain):
            # Could be problematic if the type is similar,
            # but not the same (same field/func names).
            # We do not want to accidentally delete records.
            self.message_user(request, "Object is not of type Domain", messages.ERROR)
            return

        try:
            obj.deletedInEpp()
            obj.save()
        except RegistryError as err:
            # Using variables to get past the linter
            message1 = f"Cannot delete Domain when in state {obj.state}"
            message2 = "This subdomain is being used as a hostname on another domain"
            # Human-readable mappings of ErrorCodes. Can be expanded.
            error_messages = {
                # noqa on these items as black wants to reformat to an invalid length
                ErrorCode.OBJECT_STATUS_PROHIBITS_OPERATION: message1,
                ErrorCode.OBJECT_ASSOCIATION_PROHIBITS_OPERATION: message2,
            }

            message = "Cannot connect to the registry"
            if not err.is_connection_error():
                # If nothing is found, will default to returned err
                message = error_messages.get(err.code, err)
            self.message_user(request, f"Error deleting this Domain: {message}", messages.ERROR)
        except TransitionNotAllowed:
            if obj.state == Domain.State.DELETED:
                self.message_user(
                    request,
                    "This domain is already deleted",
                    messages.INFO,
                )
            else:
                self.message_user(
                    request,
                    "Error deleting this Domain: "
                    f"Can't switch from state '{obj.state}' to 'deleted'"
                    ", must be either 'dns_needed' or 'on_hold'",
                    messages.ERROR,
                )
        except Exception:
            self.message_user(
                request,
                "Could not delete: An unspecified error occured",
                messages.ERROR,
            )
        else:
            self.message_user(
                request,
                ("Domain %s has been deleted. Thanks!") % obj.name,
            )

        return HttpResponseRedirect(".")

    def do_get_status(self, request, obj):
        try:
            statuses = obj.statuses
        except Exception as err:
            self.message_user(request, err, messages.ERROR)
        else:
            self.message_user(
                request,
                f"The registry statuses are {statuses}. These statuses are from the provider of the .gov registry.",
            )
        return HttpResponseRedirect(".")

    def do_place_client_hold(self, request, obj):
        try:
            obj.place_client_hold()
            obj.save()
        except Exception as err:
            # if error is an error from the registry, display useful
            # and readable error
            if err.code:
                self.message_user(
                    request,
                    f"Error placing the hold with the registry: {err}",
                    messages.ERROR,
                )
            elif err.is_connection_error():
                self.message_user(
                    request,
                    "Error connecting to the registry",
                    messages.ERROR,
                )
            else:
                # all other type error messages, display the error
                self.message_user(request, err, messages.ERROR)
        else:
            self.message_user(
                request,
                ("%s is in client hold. This domain is no longer accessible on the public internet.") % obj.name,
            )
        return HttpResponseRedirect(".")

    def do_remove_client_hold(self, request, obj):
        try:
            obj.revert_client_hold()
            obj.save()
        except Exception as err:
            # if error is an error from the registry, display useful
            # and readable error
            if err.code:
                self.message_user(
                    request,
                    f"Error removing the hold in the registry: {err}",
                    messages.ERROR,
                )
            elif err.is_connection_error():
                self.message_user(
                    request,
                    "Error connecting to the registry",
                    messages.ERROR,
                )
            else:
                # all other type error messages, display the error
                self.message_user(request, err, messages.ERROR)
        else:
            self.message_user(
                request,
                ("%s is ready. This domain is accessible on the public internet.") % obj.name,
            )
        return HttpResponseRedirect(".")

    def do_edit_domain(self, request, obj):
        # We want to know, globally, when an edit action occurs
        request.session["analyst_action"] = "edit"
        # Restricts this action to this domain (pk) only
        request.session["analyst_action_location"] = obj.id
        return HttpResponseRedirect(reverse("domain", args=(obj.id,)))

    def change_view(self, request, object_id):
        # If the analyst was recently editing a domain page,
        # delete any associated session values
        if "analyst_action" in request.session:
            del request.session["analyst_action"]
            del request.session["analyst_action_location"]
        return super().change_view(request, object_id)

    def has_change_permission(self, request, obj=None):
        # Fixes a bug wherein users which are only is_staff
        # can access 'change' when GET,
        # but cannot access this page when it is a request of type POST.
        if request.user.has_perm("registrar.full_access_permission") or request.user.has_perm(
            "registrar.analyst_access_permission"
        ):
            return True
        return super().has_change_permission(request, obj)


class DraftDomainAdmin(ListHeaderAdmin):
    """Custom draft domain admin class."""

    search_fields = ["name"]
    search_help_text = "Search by draft domain name."

    # this ordering effects the ordering of results
    # in autocomplete_fields for user
    ordering = ["name"]


class VerifiedByStaffAdmin(ListHeaderAdmin):
    list_display = ("email", "requestor", "truncated_notes", "created_at")
    search_fields = ["email"]
    search_help_text = "Search by email."
    list_filter = [
        "requestor",
    ]
    readonly_fields = [
        "requestor",
    ]

    def truncated_notes(self, obj):
        # Truncate the 'notes' field to 50 characters
        return str(obj.notes)[:50]

    truncated_notes.short_description = "Notes (Truncated)"  # type: ignore

    def save_model(self, request, obj, form, change):
        # Set the user field to the current admin user
        obj.requestor = request.user if request.user.is_authenticated else None
        super().save_model(request, obj, form, change)


admin.site.unregister(LogEntry)  # Unregister the default registration
admin.site.register(LogEntry, CustomLogEntryAdmin)
admin.site.register(models.User, MyUserAdmin)
# Unregister the built-in Group model
admin.site.unregister(Group)
# Register UserGroup
admin.site.register(models.UserGroup)
admin.site.register(models.UserDomainRole, UserDomainRoleAdmin)
admin.site.register(models.Contact, ContactAdmin)
admin.site.register(models.DomainInvitation, DomainInvitationAdmin)
admin.site.register(models.DomainInformation, DomainInformationAdmin)
admin.site.register(models.Domain, DomainAdmin)
admin.site.register(models.DraftDomain, DraftDomainAdmin)
# Host and HostIP removed from django admin because changes in admin
# do not propagate to registry and logic not applied
admin.site.register(models.Host, MyHostAdmin)
admin.site.register(models.Website, WebsiteAdmin)
admin.site.register(models.PublicContact, AuditedAdmin)
admin.site.register(models.DomainRequest, DomainRequestAdmin)
admin.site.register(models.TransitionDomain, TransitionDomainAdmin)
admin.site.register(models.VerifiedByStaff, VerifiedByStaffAdmin)
