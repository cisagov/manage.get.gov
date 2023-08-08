import logging
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.contenttypes.models import ContentType
from django.http.response import HttpResponseRedirect
from django.urls import reverse
from . import models

logger = logging.getLogger(__name__)


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
    

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Used to sort dropdown fields alphabetically but can be expanded upon"""
        # Determines what we want to sort by, ex: by name
        order_by_list = []
        if db_field.name == "submitter" or db_field.name == "authorizing_official" or db_field.name == "creator" or db_field.name == "investigator":
            order_by_list = ['first_name', 'last_name']
        elif db_field.name == "requested_domain":
            order_by_list = ['name']
       
        return self.formfield_order_helper(order_by_list, db_field, request, **kwargs)
    
    def formfield_order_helper(self, order_by_list, db_field, request, **kwargs):
        """A helper function to order a dropdown field in Django Admin, takes the fields you want to order by as an array"""
        formfield = super(AuditedAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)
        # Only order if we choose to do so
        if order_by_list:
            formfield.queryset = formfield.queryset.order_by(*order_by_list)

        return formfield      




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

    search_fields = ["name"]
    search_help_text = "Search by domain name."
    change_form_template = "django/admin/domain_change_form.html"
    readonly_fields = ["state"]

    def response_change(self, request, obj):
        ACTION_BUTTON = "_place_client_hold"
        if ACTION_BUTTON in request.POST:
            try:
                obj.place_client_hold()
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

        return super().response_change(request, obj)


class ContactAdmin(ListHeaderAdmin):

    """Custom contact admin class to add search."""

    search_fields = ["email", "first_name", "last_name"]
    search_help_text = "Search by firstname, lastname or email."


class DomainApplicationAdmin(ListHeaderAdmin):

    """Customize the applications listing view."""

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
    readonly_fields = [
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
        if change:  # Check if the application is being edited
            # Get the original application from the database
            original_obj = models.DomainApplication.objects.get(pk=obj.pk)

            if obj.status != original_obj.status:
                if obj.status == models.DomainApplication.STARTED:
                    # No conditions
                    pass
                elif obj.status == models.DomainApplication.SUBMITTED:
                    # This is an fsm in model which will throw an error if the
                    # transition condition is violated, so we call it on the
                    # original object which has the right status value, and pass
                    # the updated object which contains the up-to-date data
                    # for the side effects (like an email send). Same
                    # comment applies to original_obj method calls below.
                    original_obj.submit(updated_domain_application=obj)
                elif obj.status == models.DomainApplication.IN_REVIEW:
                    original_obj.in_review(updated_domain_application=obj)
                elif obj.status == models.DomainApplication.ACTION_NEEDED:
                    original_obj.action_needed(updated_domain_application=obj)
                elif obj.status == models.DomainApplication.APPROVED:
                    original_obj.approve(updated_domain_application=obj)
                elif obj.status == models.DomainApplication.WITHDRAWN:
                    original_obj.withdraw()
                elif obj.status == models.DomainApplication.REJECTED:
                    original_obj.reject(updated_domain_application=obj)
                else:
                    logger.warning("Unknown status selected in django admin")

        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            # Superusers have full access, no fields are read-only
            return []
        else:
            # Regular users can only view the specified fields
            return self.readonly_fields


admin.site.register(models.User, MyUserAdmin)
admin.site.register(models.UserDomainRole, AuditedAdmin)
admin.site.register(models.Contact, ContactAdmin)
admin.site.register(models.DomainInvitation, AuditedAdmin)
admin.site.register(models.DomainInformation, AuditedAdmin)
admin.site.register(models.Domain, DomainAdmin)
admin.site.register(models.Host, MyHostAdmin)
admin.site.register(models.Nameserver, MyHostAdmin)
admin.site.register(models.Website, AuditedAdmin)
admin.site.register(models.DomainApplication, DomainApplicationAdmin)
