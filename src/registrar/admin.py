import logging
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.contenttypes.models import ContentType
from django.http.response import HttpResponseRedirect
from django.urls import reverse
from registrar.models.utility.admin_sort_fields import AdminSortFields
from . import models
from auditlog.models import LogEntry  # type: ignore
from auditlog.admin import LogEntryAdmin  # type: ignore

logger = logging.getLogger(__name__)


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


class AuditedAdmin(admin.ModelAdmin, AdminSortFields):
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

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Used to sort dropdown fields alphabetically but can be expanded upon"""
        form_field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        return self.form_field_order_helper(form_field, db_field)


class ListHeaderAdmin(AuditedAdmin):
    """Custom admin to add a descriptive subheader to list views."""

    def changelist_view(self, request, extra_context=None):
        if extra_context is None:
            extra_context = {}
        # Get the filtered values
        filters = self.get_filters(request)
        # Pass the filtered values to the template context
        extra_context["filters"] = filters
        extra_context["search_query"] = request.GET.get(
            "q", ""
        )  # Assuming the search query parameter is 'q'
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
                parameter_name = (
                    param.replace("__exact", "")
                    .replace("_type", "")
                    .replace("__id", " id")
                )

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

    inlines = [UserContactInline]

    list_display = (
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_superuser",
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

    def get_list_display(self, request):
        if not request.user.is_superuser:
            # Customize the list display for staff users
            return ("email", "first_name", "last_name", "is_staff", "is_superuser")

        # Use the default list display for non-staff users
        return super().get_list_display(request)

    def get_fieldsets(self, request, obj=None):
        if not request.user.is_superuser:
            # If the user doesn't have permission to change the model,
            # show a read-only fieldset
            return ((None, {"fields": []}),)

        # If the user has permission to change the model, show all fields
        return super().get_fieldsets(request, obj)


class HostIPInline(admin.StackedInline):
    """Edit an ip address on the host page."""

    model = models.HostIP


class MyHostAdmin(AuditedAdmin):
    """Custom host admin class to use our inlines."""

    inlines = [HostIPInline]


class DomainAdmin(ListHeaderAdmin):
    """Custom domain admin class to add extra buttons."""

    # Columns
    list_display = [
        "name",
        "organization_type",
        "state",
    ]

    def organization_type(self, obj):
        return obj.domain_info.organization_type

    organization_type.admin_order_field = (  # type: ignore
        "domain_info__organization_type"
    )

    # Filters
    list_filter = ["domain_info__organization_type"]

    search_fields = ["name"]
    search_help_text = "Search by domain name."
    change_form_template = "django/admin/domain_change_form.html"
    readonly_fields = ["state"]

    def response_change(self, request, obj):
        # Create dictionary of action functions
        ACTION_FUNCTIONS = {
            "_place_client_hold": self.do_place_client_hold,
            "_remove_client_hold": self.do_remove_client_hold,
            "_edit_domain": self.do_edit_domain,
            "_delete_domain": self.do_delete_domain,
            "_get_status": self.do_get_status,
        }

        # Check which action button was pressed and call the corresponding function
        for action, function in ACTION_FUNCTIONS.items():
            if action in request.POST:
                return function(request, obj)

        # If no matching action button is found, return the super method
        return super().response_change(request, obj)

    def do_delete_domain(self, request, obj):
        try:
            obj.deleted()
            obj.save()
        except Exception as err:
            self.message_user(request, err, messages.ERROR)
        else:
            self.message_user(
                request,
                ("Domain %s Should now be deleted " ". Thanks!") % obj.name,
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
                ("Domain statuses are %s" ". Thanks!") % statuses,
            )
        return HttpResponseRedirect(".")

    def do_place_client_hold(self, request, obj):
        try:
            obj.place_client_hold()
            obj.save()
        except Exception as err:
            self.message_user(request, err, messages.ERROR)
        else:
            self.message_user(
                request,
                (
                    "%s is in client hold. This domain is no longer accessible on"
                    " the public internet."
                )
                % obj.name,
            )
        return HttpResponseRedirect(".")

    def do_remove_client_hold(self, request, obj):
        try:
            obj.revertClientHold()
            obj.save()
        except Exception as err:
            self.message_user(request, err, messages.ERROR)
        else:
            self.message_user(
                request,
                ("%s is ready. This domain is accessible on the public internet.")
                % obj.name,
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
        if request.user.is_staff:
            return True
        return super().has_change_permission(request, obj)


class ContactAdmin(ListHeaderAdmin):
    """Custom contact admin class to add search."""

    search_fields = ["email", "first_name", "last_name"]
    search_help_text = "Search by firstname, lastname or email."
    list_display = [
        "contact",
        "email",
    ]

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


class WebsiteAdmin(ListHeaderAdmin):
    """Custom website admin class."""

    # Search
    search_fields = [
        "website",
    ]
    search_help_text = "Search by website."


class UserDomainRoleAdmin(ListHeaderAdmin):
    """Custom domain role admin class."""

    # Columns
    list_display = [
        "user",
        "domain",
        "role",
    ]

    # Search
    search_fields = [
        "user__first_name",
        "user__last_name",
        "domain__name",
        "role",
    ]
    search_help_text = "Search by user, domain, or role."


class DomainInvitationAdmin(ListHeaderAdmin):
    """Custom domain invitation admin class."""

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
    search_help_text = "Search by email or domain."


class DomainInformationAdmin(ListHeaderAdmin):
    """Customize domain information admin class."""

    # Columns
    list_display = [
        "domain",
        "organization_type",
        "created_at",
        "submitter",
    ]

    # Filters
    list_filter = ["organization_type"]

    # Search
    search_fields = [
        "domain__name",
    ]
    search_help_text = "Search by domain."


class DomainApplicationAdmin(ListHeaderAdmin):

    """Custom domain applications admin class."""

    # Set multi-selects 'read-only' (hide selects and show data)
    # based on user perms and application creator's status
    # form = DomainApplicationForm

    # Columns
    list_display = [
        "requested_domain",
        "status",
        "organization_type",
        "created_at",
        "submitter",
        "investigator",
    ]

    # Filters
    list_filter = ("status", "organization_type", "investigator")

    # Search
    search_fields = [
        "requested_domain__name",
        "submitter__email",
        "submitter__first_name",
        "submitter__last_name",
    ]
    search_help_text = "Search by domain or submitter."

    # Detail view
    fieldsets = [
        (None, {"fields": ["status", "investigator", "creator"]}),
        (
            "Type of organization",
            {
                "fields": [
                    "organization_type",
                    "federally_recognized_tribe",
                    "state_recognized_tribe",
                    "tribe_name",
                    "federal_agency",
                    "federal_type",
                    "is_election_board",
                    "type_of_work",
                    "more_organization_information",
                ]
            },
        ),
        (
            "Organization name and mailing address",
            {
                "fields": [
                    "organization_name",
                    "address_line1",
                    "address_line2",
                    "city",
                    "state_territory",
                    "zipcode",
                    "urbanization",
                ]
            },
        ),
        ("Authorizing official", {"fields": ["authorizing_official"]}),
        ("Current websites", {"fields": ["current_websites"]}),
        (".gov domain", {"fields": ["requested_domain", "alternative_domains"]}),
        ("Purpose of your domain", {"fields": ["purpose"]}),
        ("Your contact information", {"fields": ["submitter"]}),
        ("Other employees from your organization?", {"fields": ["other_contacts"]}),
        (
            "No other employees from your organization?",
            {"fields": ["no_other_contacts_rationale"]},
        ),
        ("Anything else we should know?", {"fields": ["anything_else"]}),
        (
            "Requirements for operating .gov domains",
            {"fields": ["is_policy_acknowledged"]},
        ),
    ]

    # Read only that we'll leverage for CISA Analysts
    analyst_readonly_fields = [
        "creator",
        "type_of_work",
        "more_organization_information",
        "address_line1",
        "address_line2",
        "zipcode",
        "requested_domain",
        "alternative_domains",
        "purpose",
        "submitter",
        "no_other_contacts_rationale",
        "anything_else",
        "is_policy_acknowledged",
    ]

    # Trigger action when a fieldset is changed
    def save_model(self, request, obj, form, change):
        if obj and obj.creator.status != models.User.RESTRICTED:
            if change:  # Check if the application is being edited
                # Get the original application from the database
                original_obj = models.DomainApplication.objects.get(pk=obj.pk)

                if obj.status != original_obj.status:
                    status_method_mapping = {
                        models.DomainApplication.STARTED: None,
                        models.DomainApplication.SUBMITTED: obj.submit,
                        models.DomainApplication.IN_REVIEW: obj.in_review,
                        models.DomainApplication.ACTION_NEEDED: obj.action_needed,
                        models.DomainApplication.APPROVED: obj.approve,
                        models.DomainApplication.WITHDRAWN: obj.withdraw,
                        models.DomainApplication.REJECTED: obj.reject,
                        models.DomainApplication.INELIGIBLE: obj.reject_with_prejudice,
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
                "This action is not permitted for applications "
                + "with a restricted creator.",
            )

    def get_readonly_fields(self, request, obj=None):
        """Set the read-only state on form elements.
        We have 2 conditions that determine which fields are read-only:
        admin user permissions and the application creator's status, so
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
            readonly_fields.extend(
                ["current_websites", "other_contacts", "alternative_domains"]
            )

        if request.user.is_superuser:
            return readonly_fields
        else:
            readonly_fields.extend([field for field in self.analyst_readonly_fields])
            return readonly_fields

    def display_restricted_warning(self, request, obj):
        if obj and obj.creator.status == models.User.RESTRICTED:
            messages.warning(
                request,
                "Cannot edit an application with a restricted creator.",
            )

    def change_view(self, request, object_id, form_url="", extra_context=None):
        obj = self.get_object(request, object_id)
        self.display_restricted_warning(request, obj)
        return super().change_view(request, object_id, form_url, extra_context)


admin.site.unregister(LogEntry)  # Unregister the default registration
admin.site.register(LogEntry, CustomLogEntryAdmin)
admin.site.register(models.User, MyUserAdmin)
admin.site.register(models.UserDomainRole, UserDomainRoleAdmin)
admin.site.register(models.Contact, ContactAdmin)
admin.site.register(models.DomainInvitation, DomainInvitationAdmin)
admin.site.register(models.DomainInformation, DomainInformationAdmin)
admin.site.register(models.Domain, DomainAdmin)
admin.site.register(models.Host, MyHostAdmin)
admin.site.register(models.Nameserver, MyHostAdmin)
admin.site.register(models.Website, WebsiteAdmin)
admin.site.register(models.PublicContact, AuditedAdmin)
admin.site.register(models.DomainApplication, DomainApplicationAdmin)
admin.site.register(models.TransitionDomain, AuditedAdmin)
