from datetime import date
import logging
import copy

from django import forms
from django.db.models import Value, CharField, Q
from django.db.models.functions import Concat, Coalesce
from django.http import HttpResponseRedirect
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
from registrar.utility.errors import FSMDomainRequestError, FSMErrorCodes
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
from django_admin_multiple_choice_list_filter.list_filters import MultipleChoiceListFilter

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

    def __init__(self, *args, **kwargs):
        """Custom init to modify the user form"""
        super(MyUserAdminForm, self).__init__(*args, **kwargs)
        self._override_base_help_texts()

    def _override_base_help_texts(self):
        """
        Used to override pre-existing help texts in AbstractUser.
        This is done to avoid modifying the base AbstractUser class.
        """
        is_superuser = self.fields.get("is_superuser")
        is_staff = self.fields.get("is_staff")
        password = self.fields.get("password")

        if is_superuser is not None:
            is_superuser.help_text = "For development purposes only; provides superuser access on the database level."

        if is_staff is not None:
            is_staff.help_text = "Designates whether the user can log in to this admin site."

        if password is not None:
            # Link is copied from the base implementation of UserChangeForm.
            link = f"../../{self.instance.pk}/password/"
            password.help_text = (
                "Raw passwords are not stored, so they will not display here. "
                f'You can change the password using <a href="{link}">this form</a>.'
            )


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

            if domain_request.investigator is not None:
                transitions = get_available_FIELD_transitions(
                    domain_request, models.DomainRequest._meta.get_field("status")
                )
            else:
                transitions = self.get_custom_field_transitions(
                    domain_request, models.DomainRequest._meta.get_field("status")
                )

            for transition in transitions:
                available_transitions.append((transition.target, transition.target.label))

            # only set the available transitions if the user is not restricted
            # from editing the domain request; otherwise, the form will be
            # readonly and the status field will not have a widget
            if not domain_request.creator.is_restricted():
                self.fields["status"].widget.choices = available_transitions

    def get_custom_field_transitions(self, instance, field):
        """Custom implementation of get_available_FIELD_transitions
        in the FSM. Allows us to still display fields filtered out by a condition."""
        curr_state = field.get_state(instance)
        transitions = field.transitions[instance.__class__]

        for name, transition in transitions.items():
            meta = transition._django_fsm
            if meta.has_transition(curr_state):
                yield meta.get_transition(curr_state)

    def clean(self):
        """
        Override of the default clean on the form.
        This is so we can inject custom form-level error messages.
        """
        # clean is called from clean_forms, which is called from is_valid
        # after clean_fields.  it is used to determine form level errors.
        # is_valid is typically called from view during a post
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        investigator = cleaned_data.get("investigator")
        rejection_reason = cleaned_data.get("rejection_reason")

        # Get the old status
        initial_status = self.initial.get("status", None)

        # We only care about investigator when in these statuses
        checked_statuses = [
            DomainRequest.DomainRequestStatus.APPROVED,
            DomainRequest.DomainRequestStatus.IN_REVIEW,
            DomainRequest.DomainRequestStatus.ACTION_NEEDED,
            DomainRequest.DomainRequestStatus.REJECTED,
            DomainRequest.DomainRequestStatus.INELIGIBLE,
        ]

        # If a status change occured, check for validity
        if status != initial_status and status in checked_statuses:
            # Checks the "investigators" field for validity.
            # That field must obey certain conditions when an domain request is approved.
            # Will call "add_error" if any issues are found.
            self._check_for_valid_investigator(investigator)

        # If the status is rejected, a rejection reason must exist
        if status == DomainRequest.DomainRequestStatus.REJECTED:
            self._check_for_valid_rejection_reason(rejection_reason)

        return cleaned_data

    def _check_for_valid_rejection_reason(self, rejection_reason) -> bool:
        """
        Checks if the rejection_reason field is not none.
        Adds form errors on failure.
        """
        is_valid = False

        # Check if a rejection reason exists. Rejection is not possible without one.
        error_message = None
        if rejection_reason is None or rejection_reason == "":
            # Lets grab the error message from a common location
            error_message = FSMDomainRequestError.get_error_message(FSMErrorCodes.NO_REJECTION_REASON)
        else:
            is_valid = True

        if error_message is not None:
            self.add_error("rejection_reason", error_message)

        return is_valid

    def _check_for_valid_investigator(self, investigator) -> bool:
        """
        Checks if the investigator field is not none, and is staff.
        Adds form errors on failure.
        """

        is_valid = False

        # Check if an investigator is assigned. No approval is possible without one.
        error_message = None
        if investigator is None:
            # Lets grab the error message from a common location
            error_message = FSMDomainRequestError.get_error_message(FSMErrorCodes.NO_INVESTIGATOR)
        elif not investigator.is_staff:
            error_message = FSMDomainRequestError.get_error_message(FSMErrorCodes.INVESTIGATOR_NOT_STAFF)
        else:
            is_valid = True

        if error_message is not None:
            self.add_error("investigator", error_message)

        return is_valid


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

    # We name the custom prop 'created_at' because linter
    # is not allowing a short_description attr on it
    # This gets around the linter limitation, for now.
    @admin.display(description=_("Created at"))
    def created(self, obj):
        return obj.timestamp

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
        "overridden_email_field",
        "first_name",
        "last_name",
        # Group is a custom property defined within this file,
        # rather than in a model like the other properties
        "group",
        "status",
    )

    # Renames inherited AbstractUser label 'email_address to 'email'
    def formfield_for_dbfield(self, dbfield, **kwargs):
        field = super().formfield_for_dbfield(dbfield, **kwargs)
        if dbfield.name == "email":
            field.label = "Email"
        return field

    # Renames inherited AbstractUser column name 'email_address to 'email'
    @admin.display(description=_("Email"))
    def overridden_email_field(self, obj):
        return obj.email

    fieldsets = (
        (
            None,
            {"fields": ("username", "password", "status", "verification_type")},
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

    readonly_fields = ("verification_type",)

    # Hide Username (uuid), Groups and Permissions
    # Q: Now that we're using Groups and Permissions,
    # do we expose those to analysts to view?
    analyst_fieldsets = (
        (
            None,
            {"fields": ("status", "verification_type",)},
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
    search_help_text = "Search by first name, last name, or email."

    change_form_template = "django/admin/email_clipboard_change_form.html"

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
        readonly_fields = list(self.readonly_fields)

        if request.user.has_perm("registrar.full_access_permission"):
            return readonly_fields
        else:
            # Return restrictive Read-only fields for analysts and
            # users who might not belong to groups
            return self.analyst_readonly_fields


class HostIPInline(admin.StackedInline):
    """Edit an ip address on the host page."""

    model = models.HostIP


class MyHostAdmin(AuditedAdmin):
    """Custom host admin class to use our inlines."""

    search_fields = ["name", "domain__name"]
    search_help_text = "Search by domain or host name."
    inlines = [HostIPInline]


class ContactAdmin(ListHeaderAdmin):
    """Custom contact admin class to add search."""

    search_fields = ["email", "first_name", "last_name"]
    search_help_text = "Search by first name, last name or email."
    list_display = [
        "name",
        "email",
        "user_exists",
    ]
    # this ordering effects the ordering of results
    # in autocomplete_fields for user
    ordering = ["first_name", "last_name", "email"]

    fieldsets = [
        (
            None,
            {"fields": ["user", "first_name", "middle_name", "last_name", "title", "email", "phone"]},
        )
    ]

    autocomplete_fields = ["user"]

    change_form_template = "django/admin/email_clipboard_change_form.html"

    def user_exists(self, obj):
        """Check if the Contact has a related User"""
        return "Yes" if obj.user is not None else "No"

    user_exists.short_description = "Is user"  # type: ignore
    user_exists.admin_order_field = "user"  # type: ignore

    # We name the custom prop 'contact' because linter
    # is not allowing a short_description attr on it
    # This gets around the linter limitation, for now.
    def name(self, obj: models.Contact):
        """Duplicate the contact _str_"""
        if obj.first_name or obj.last_name:
            return obj.get_formatted_name()
        elif obj.email:
            return obj.email
        elif obj.pk:
            return str(obj.pk)
        else:
            return ""

    name.admin_order_field = "first_name"  # type: ignore

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

    def get_model_perms(self, request):
        """
        Return empty perms dict thus hiding the model from admin index.
        """
        superuser_perm = request.user.has_perm("registrar.full_access_permission")
        analyst_perm = request.user.has_perm("registrar.analyst_access_permission")
        if analyst_perm and not superuser_perm:
            return {}
        return super().get_model_perms(request)

    def has_change_permission(self, request, obj=None):
        """
        Allow analysts to access the change form directly via URL.
        """
        superuser_perm = request.user.has_perm("registrar.full_access_permission")
        analyst_perm = request.user.has_perm("registrar.analyst_access_permission")
        if analyst_perm and not superuser_perm:
            return True
        return super().has_change_permission(request, obj)

    def response_change(self, request, obj):
        """
        Override to redirect users back to the previous page after saving.
        """
        superuser_perm = request.user.has_perm("registrar.full_access_permission")
        analyst_perm = request.user.has_perm("registrar.analyst_access_permission")
        return_path = request.GET.get("return_path")

        # First, call the super method to perform the standard operations and capture the response
        response = super().response_change(request, obj)

        # Don't redirect to the website page on save if the user is an analyst.
        # Rather, just redirect back to the originating page.
        if (analyst_perm and not superuser_perm) and return_path:
            # Redirect to the return path if it exists
            return HttpResponseRedirect(return_path)

        # If no redirection is needed, return the original response
        return response


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
    search_help_text = "Search by first name, last name, email, or domain."

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

    change_form_template = "django/admin/email_clipboard_change_form.html"


class DomainInformationAdmin(ListHeaderAdmin):
    """Customize domain information admin class."""

    form = DomainInformationAdminForm

    # Columns
    list_display = [
        "domain",
        "generic_org_type",
        "created_at",
        "submitter",
    ]

    orderable_fk_fields = [
        ("domain", "name"),
        ("submitter", ["first_name", "last_name"]),
    ]

    # Filters
    list_filter = ["generic_org_type"]

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
                    "generic_org_type",
                    "is_election_board",
                    "organization_type",
                ]
            },
        ),
        (
            "More details",
            {
                "classes": ["collapse"],
                "fields": [
                    "federal_type",
                    # "updated_federal_agency",
                    # Above field commented out so it won't display
                    "federal_agency",  # TODO: remove later
                    "tribe_name",
                    "federally_recognized_tribe",
                    "state_recognized_tribe",
                    "about_your_organization",
                ],
            },
        ),
        (
            "Organization name and mailing address",
            {
                "fields": [
                    "organization_name",
                    "state_territory",
                ]
            },
        ),
        (
            "More details",
            {
                "classes": ["collapse"],
                "fields": [
                    "address_line1",
                    "address_line2",
                    "city",
                    "zipcode",
                    "urbanization",
                ],
            },
        ),
    ]

    # Readonly fields for analysts and superusers
    readonly_fields = ("other_contacts", "generic_org_type", "is_election_board")

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

    change_form_template = "django/admin/domain_information_change_form.html"

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
    change_form_template = "django/admin/domain_request_change_form.html"

    class StatusListFilter(MultipleChoiceListFilter):
        """Custom status filter which is a multiple choice filter"""

        title = "Status"
        parameter_name = "status__in"

        template = "django/admin/multiple_choice_list_filter.html"

        def lookups(self, request, model_admin):
            return DomainRequest.DomainRequestStatus.choices

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
        "submission_date",
        "status",
        "generic_org_type",
        "federal_type",
        "federal_agency",
        "organization_name",
        "custom_election_board",
        "city",
        "state_territory",
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
        StatusListFilter,
        "generic_org_type",
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
        (
            None,
            {
                "fields": [
                    "status",
                    "rejection_reason",
                    "investigator",
                    "creator",
                    "submitter",
                    "approved_domain",
                    "notes",
                ]
            },
        ),
        (".gov domain", {"fields": ["requested_domain", "alternative_domains"]}),
        (
            "Contacts",
            {
                "fields": [
                    "authorizing_official",
                    "other_contacts",
                    "no_other_contacts_rationale",
                    "cisa_representative_email",
                ]
            },
        ),
        ("Background info", {"fields": ["purpose", "anything_else", "current_websites"]}),
        (
            "Type of organization",
            {
                "fields": [
                    "generic_org_type",
                    "is_election_board",
                    "organization_type",
                ]
            },
        ),
        (
            "More details",
            {
                "classes": ["collapse"],
                "fields": [
                    "federal_type",
                    # "updated_federal_agency",
                    # Above field commented out so it won't display
                    "federal_agency",  # TODO: remove later
                    "tribe_name",
                    "federally_recognized_tribe",
                    "state_recognized_tribe",
                    "about_your_organization",
                ],
            },
        ),
        (
            "Organization name and mailing address",
            {
                "fields": [
                    "organization_name",
                    "state_territory",
                ]
            },
        ),
        (
            "More details",
            {
                "classes": ["collapse"],
                "fields": [
                    "address_line1",
                    "address_line2",
                    "city",
                    "zipcode",
                    "urbanization",
                ],
            },
        ),
    ]

    # Readonly fields for analysts and superusers
    readonly_fields = (
        "other_contacts",
        "current_websites",
        "alternative_domains",
        "generic_org_type",
        "is_election_board",
    )

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
        "cisa_representative_email",
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
    # NOTE: This impacts the select2 dropdowns (combobox)
    # Currentl, there's only one for requests on DomainInfo
    ordering = ["-submission_date", "requested_domain__name"]

    change_form_template = "django/admin/domain_request_change_form.html"

    # Trigger action when a fieldset is changed
    def save_model(self, request, obj, form, change):
        """Custom save_model definition that handles edge cases"""

        # == Check that the obj is in a valid state == #

        # If obj is none, something went very wrong.
        # The form should have blocked this, so lets forbid it.
        if not obj:
            logger.error(f"Invalid value for obj ({obj})")
            messages.set_level(request, messages.ERROR)
            messages.error(
                request,
                "Could not save DomainRequest. Something went wrong.",
            )
            return None

        # If the user is restricted or we're saving an invalid model,
        # forbid this action.
        if not obj or obj.creator.status == models.User.RESTRICTED:
            # Clear the success message
            messages.set_level(request, messages.ERROR)

            messages.error(
                request,
                "This action is not permitted for domain requests with a restricted creator.",
            )

            return None

        # == Check if we're making a change or not == #

        # If we're not making a change (adding a record), run save model as we do normally
        if not change:
            return super().save_model(request, obj, form, change)

        # == Handle non-status changes == #

        # Get the original domain request from the database.
        original_obj = models.DomainRequest.objects.get(pk=obj.pk)
        if obj.status == original_obj.status:
            # If the status hasn't changed, let the base function take care of it
            return super().save_model(request, obj, form, change)

        # == Handle status changes == #

        # Run some checks on the current object for invalid status changes
        obj, should_save = self._handle_status_change(request, obj, original_obj)

        # We should only save if we don't display any errors in the step above.
        if should_save:
            return super().save_model(request, obj, form, change)

    def _handle_status_change(self, request, obj, original_obj):
        """
        Checks for various conditions when a status change is triggered.
        In the event that it is valid, the status will be mapped to
        the appropriate method.

        In the event that we should not status change, an error message
        will be displayed.

        Returns a tuple: (obj: DomainRequest, should_proceed: bool)
        """

        should_proceed = True
        error_message = None

        # Get the method that should be run given the status
        selected_method = self.get_status_method_mapping(obj)
        if selected_method is None:
            logger.warning("Unknown status selected in django admin")

            # If the status is not mapped properly, saving could cause
            # weird issues down the line. Instead, we should block this.
            should_proceed = False
            return should_proceed

        request_is_not_approved = obj.status != models.DomainRequest.DomainRequestStatus.APPROVED
        if request_is_not_approved and not obj.domain_is_not_active():
            # If an admin tried to set an approved domain request to
            # another status and the related domain is already
            # active, shortcut the action and throw a friendly
            # error message. This action would still not go through
            # shortcut or not as the rules are duplicated on the model,
            # but the error would be an ugly Django error screen.
            error_message = "This action is not permitted. The domain is already active."
        elif obj.status == models.DomainRequest.DomainRequestStatus.REJECTED and not obj.rejection_reason:
            # This condition should never be triggered.
            # The opposite of this condition is acceptable (rejected -> other status and rejection_reason)
            # because we clean up the rejection reason in the transition in the model.
            error_message = FSMDomainRequestError.get_error_message(FSMErrorCodes.NO_REJECTION_REASON)
        else:
            # This is an fsm in model which will throw an error if the
            # transition condition is violated, so we roll back the
            # status to what it was before the admin user changed it and
            # let the fsm method set it.
            obj.status = original_obj.status

            # Try to perform the status change.
            # Catch FSMDomainRequestError's and return the message,
            # as these are typically user errors.
            try:
                selected_method()
            except FSMDomainRequestError as err:
                logger.warning(f"An error encountered when trying to change status: {err}")
                error_message = err.message

        if error_message is not None:
            # Clear the success message
            messages.set_level(request, messages.ERROR)
            # Display the error
            messages.error(
                request,
                error_message,
            )

            # If an error message exists, we shouldn't proceed
            should_proceed = False

        return (obj, should_proceed)

    def get_status_method_mapping(self, domain_request):
        """Returns what method should be ran given an domain request object"""
        # Define a per-object mapping
        status_method_mapping = {
            models.DomainRequest.DomainRequestStatus.STARTED: None,
            models.DomainRequest.DomainRequestStatus.SUBMITTED: domain_request.submit,
            models.DomainRequest.DomainRequestStatus.IN_REVIEW: domain_request.in_review,
            models.DomainRequest.DomainRequestStatus.ACTION_NEEDED: domain_request.action_needed,
            models.DomainRequest.DomainRequestStatus.APPROVED: domain_request.approve,
            models.DomainRequest.DomainRequestStatus.WITHDRAWN: domain_request.withdraw,
            models.DomainRequest.DomainRequestStatus.REJECTED: domain_request.reject,
            models.DomainRequest.DomainRequestStatus.INELIGIBLE: (domain_request.reject_with_prejudice),
        }

        # Grab the method
        return status_method_mapping.get(domain_request.status, None)

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
            readonly_fields.extend(["alternative_domains"])

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

    def changelist_view(self, request, extra_context=None):
        """
        Override changelist_view to set the selected value of status filter.
        """
        # there are two conditions which should set the default selected filter:
        # 1 - there are no query parameters in the request and the request is the
        #     initial request for this view
        # 2 - there are no query parameters in the request and the referring url is
        #     the change view for a domain request
        should_apply_default_filter = False
        # use http_referer in order to distinguish between request as a link from another page
        # and request as a removal of all filters
        http_referer = request.META.get("HTTP_REFERER", "")
        # if there are no query parameters in the request
        if not bool(request.GET):
            # if the request is the initial request for this view
            if request.path not in http_referer:
                should_apply_default_filter = True
            # elif the request is a referral from changelist view or from
            # domain request change view
            elif request.path in http_referer:
                # find the index to determine the referring url after the path
                index = http_referer.find(request.path)
                # Check if there is a character following the path in http_referer
                next_char_index = index + len(request.path)
                if index + next_char_index < len(http_referer):
                    next_char = http_referer[next_char_index]

                    # Check if the next character is a digit, if so, this indicates
                    # a change view for domain request
                    if next_char.isdigit():
                        should_apply_default_filter = True

        if should_apply_default_filter:
            # modify the GET of the request to set the selected filter
            modified_get = copy.deepcopy(request.GET)
            modified_get["status__in"] = "submitted,in review,action needed"
            request.GET = modified_get
        response = super().changelist_view(request, extra_context=extra_context)
        return response

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

    change_form_template = "django/admin/email_clipboard_change_form.html"


class DomainInformationInline(admin.StackedInline):
    """Edit a domain information on the domain page.
    We had issues inheriting from both StackedInline
    and the source DomainInformationAdmin since these
    classes conflict, so we'll just pull what we need
    from DomainInformationAdmin
    """

    form = DomainInformationInlineForm
    template = "django/admin/includes/domain_info_inline_stacked.html"
    model = models.DomainInformation

    fieldsets = copy.deepcopy(DomainInformationAdmin.fieldsets)
    # remove .gov domain from fieldset
    for index, (title, f) in enumerate(fieldsets):
        if title == ".gov domain":
            del fieldsets[index]
            break

    readonly_fields = DomainInformationAdmin.readonly_fields
    analyst_readonly_fields = DomainInformationAdmin.analyst_readonly_fields

    autocomplete_fields = [
        "creator",
        "domain_request",
        "authorizing_official",
        "domain",
        "submitter",
    ]

    def has_change_permission(self, request, obj=None):
        """Custom has_change_permission override so that we can specify that
        analysts can edit this through this inline, but not through the model normally"""

        superuser_perm = request.user.has_perm("registrar.full_access_permission")
        analyst_perm = request.user.has_perm("registrar.analyst_access_permission")
        if analyst_perm and not superuser_perm:
            return True
        return super().has_change_permission(request, obj)

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
            if self.value() == "1":
                return queryset.filter(domain_info__is_election_board=True)
            if self.value() == "0":
                return queryset.filter(Q(domain_info__is_election_board=False) | Q(domain_info__is_election_board=None))

    inlines = [DomainInformationInline]

    # Columns
    list_display = [
        "name",
        "generic_org_type",
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

    def generic_org_type(self, obj):
        return obj.domain_info.get_generic_org_type_display()

    generic_org_type.admin_order_field = "domain_info__generic_org_type"  # type: ignore

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

    @admin.display(description=_("State / territory"))
    def state_territory(self, obj):
        return obj.domain_info.state_territory if obj.domain_info else None

    state_territory.admin_order_field = "domain_info__state_territory"  # type: ignore

    # Filters
    list_filter = ["domain_info__generic_org_type", "domain_info__federal_type", ElectionOfficeFilter, "state"]

    search_fields = ["name"]
    search_help_text = "Search by domain name."
    change_form_template = "django/admin/domain_change_form.html"
    readonly_fields = ["state", "expiration_date", "first_ready", "deleted"]

    # Table ordering
    ordering = ["name"]

    # Override for the delete confirmation page on the domain table (bulk delete action)
    delete_selected_confirmation_template = "django/admin/domain_delete_selected_confirmation.html"

    def delete_view(self, request, object_id, extra_context=None):
        """
        Custom delete_view to perform additional actions or customize the template.
        """

        # Set the delete template to a custom one
        self.delete_confirmation_template = "django/admin/domain_delete_confirmation.html"
        response = super().delete_view(request, object_id, extra_context=extra_context)

        return response

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        """Custom changeform implementation to pass in context information"""
        if extra_context is None:
            extra_context = {}

        if object_id is not None:
            domain = Domain.objects.get(pk=object_id)

            # Used in the custom contact view
            if domain is not None and hasattr(domain, "domain_info"):
                extra_context["original_object"] = domain.domain_info

            extra_context["state_help_message"] = Domain.State.get_admin_help_text(domain.state)
            extra_context["domain_state"] = domain.get_state_display()

            # Pass in what the an extended expiration date would be for the expiration date modal
            self._set_expiration_date_context(domain, extra_context)

        return super().changeform_view(request, object_id, form_url, extra_context)

    def _set_expiration_date_context(self, domain, extra_context):
        """Given a domain, calculate the an extended expiration date
        from the current registry expiration date."""
        years_to_extend_by = self._get_calculated_years_for_exp_date(domain)
        try:
            curr_exp_date = domain.registry_expiration_date
        except KeyError:
            # No expiration date was found. Return none.
            extra_context["extended_expiration_date"] = None
        else:
            new_date = curr_exp_date + relativedelta(years=years_to_extend_by)
            extra_context["extended_expiration_date"] = new_date

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
                    (
                        "Error deleting this Domain: "
                        f"Can't switch from state '{obj.state}' to 'deleted'"
                        ", must be either 'dns_needed' or 'on_hold'"
                    ),
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
                "Domain %s has been deleted. Thanks!" % obj.name,
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
                "%s is in client hold. This domain is no longer accessible on the public internet." % obj.name,
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
                "%s is ready. This domain is accessible on the public internet." % obj.name,
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
    list_display = ["name"]

    @admin.display(description=_("Requested domain"))
    def name(self, obj):
        return obj.name

    def get_model_perms(self, request):
        """
        Return empty perms dict thus hiding the model from admin index.
        """
        superuser_perm = request.user.has_perm("registrar.full_access_permission")
        analyst_perm = request.user.has_perm("registrar.analyst_access_permission")
        if analyst_perm and not superuser_perm:
            return {}
        return super().get_model_perms(request)

    def has_change_permission(self, request, obj=None):
        """
        Allow analysts to access the change form directly via URL.
        """
        superuser_perm = request.user.has_perm("registrar.full_access_permission")
        analyst_perm = request.user.has_perm("registrar.analyst_access_permission")
        if analyst_perm and not superuser_perm:
            return True
        return super().has_change_permission(request, obj)

    def response_change(self, request, obj):
        """
        Override to redirect users back to the previous page after saving.
        """
        superuser_perm = request.user.has_perm("registrar.full_access_permission")
        analyst_perm = request.user.has_perm("registrar.analyst_access_permission")
        return_path = request.GET.get("return_path")

        # First, call the super method to perform the standard operations and capture the response
        response = super().response_change(request, obj)

        # Don't redirect to the website page on save if the user is an analyst.
        # Rather, just redirect back to the originating page.
        if (analyst_perm and not superuser_perm) and return_path:
            # Redirect to the return path if it exists
            return HttpResponseRedirect(return_path)

        # If no redirection is needed, return the original response
        return response


class PublicContactAdmin(ListHeaderAdmin):
    """Custom PublicContact admin class."""

    change_form_template = "django/admin/email_clipboard_change_form.html"
    autocomplete_fields = ["domain"]


class VerifiedByStaffAdmin(ListHeaderAdmin):
    list_display = ("email", "requestor", "truncated_notes", "created_at")
    search_fields = ["email"]
    search_help_text = "Search by email."
    readonly_fields = [
        "requestor",
    ]

    change_form_template = "django/admin/email_clipboard_change_form.html"

    def truncated_notes(self, obj):
        # Truncate the 'notes' field to 50 characters
        return str(obj.notes)[:50]

    truncated_notes.short_description = "Notes (Truncated)"  # type: ignore

    def save_model(self, request, obj, form, change):
        # Set the user field to the current admin user
        obj.requestor = request.user if request.user.is_authenticated else None
        super().save_model(request, obj, form, change)


class FederalAgencyAdmin(ListHeaderAdmin):
    list_display = ["agency"]
    search_fields = ["agency"]
    search_help_text = "Search by agency name."
    ordering = ["agency"]


class UserGroupAdmin(AuditedAdmin):
    """Overwrite the generated UserGroup admin class"""

    list_display = ["user_group"]

    fieldsets = ((None, {"fields": ("name", "permissions")}),)

    def formfield_for_dbfield(self, dbfield, **kwargs):
        field = super().formfield_for_dbfield(dbfield, **kwargs)
        if dbfield.name == "name":
            field.label = "Group name"
        if dbfield.name == "permissions":
            field.label = "User permissions"
        return field

    # We name the custom prop 'Group' because linter
    # is not allowing a short_description attr on it
    # This gets around the linter limitation, for now.
    @admin.display(description=_("Group"))
    def user_group(self, obj):
        return obj.name


admin.site.unregister(LogEntry)  # Unregister the default registration
admin.site.register(LogEntry, CustomLogEntryAdmin)
admin.site.register(models.User, MyUserAdmin)
# Unregister the built-in Group model
admin.site.unregister(Group)
# Register UserGroup
admin.site.register(models.UserGroup, UserGroupAdmin)
admin.site.register(models.UserDomainRole, UserDomainRoleAdmin)
admin.site.register(models.Contact, ContactAdmin)
admin.site.register(models.DomainInvitation, DomainInvitationAdmin)
admin.site.register(models.DomainInformation, DomainInformationAdmin)
admin.site.register(models.Domain, DomainAdmin)
admin.site.register(models.DraftDomain, DraftDomainAdmin)
admin.site.register(models.FederalAgency, FederalAgencyAdmin)
# Host and HostIP removed from django admin because changes in admin
# do not propagate to registry and logic not applied
admin.site.register(models.Host, MyHostAdmin)
admin.site.register(models.Website, WebsiteAdmin)
admin.site.register(models.PublicContact, PublicContactAdmin)
admin.site.register(models.DomainRequest, DomainRequestAdmin)
admin.site.register(models.TransitionDomain, TransitionDomainAdmin)
admin.site.register(models.VerifiedByStaff, VerifiedByStaffAdmin)
