import logging
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.contenttypes.models import ContentType
from django.http.response import HttpResponseRedirect
from django.urls import reverse
from registrar.models.utility.admin_sort_fields import AdminSortFields
from . import models

logger = logging.getLogger(__name__)


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

    search_fields = ["name"]
    search_help_text = "Search by domain name."
    change_form_template = "django/admin/domain_change_form.html"
    readonly_fields = ["state"]

    def response_change(self, request, obj):
        print(request.POST)
        ACTION_BUTTON = "_place_client_hold"
        GET_SECURITY_EMAIL="_get_security_email"
        SET_SECURITY_CONTACT="_set_security_contact"
        MAKE_DOMAIN="_make_domain_in_registry"
        logger.info("in response")
        if ACTION_BUTTON in request.POST:
            logger.info("in action button")
            print("in action button")
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
   
        if GET_SECURITY_EMAIL in request.POST:
            try:
               security_email=obj.get_security_email()
               
               
            except Exception as err:
                self.message_user(request, err, messages.ERROR)
            else:
                self.message_user(request,
                    (
                        "The security email is %"
                        ". Thanks!"
                    )
                    % security_email,
                )
            return HttpResponseRedirect(".")

           
        if SET_SECURITY_CONTACT in request.POST:
            try:
               security_contact = obj.get_default_security_contact()
               security_contact.email="ab@test.gov"
               
               obj.security_contact=security_contact
            except Exception as err:
                self.message_user(request, err, messages.ERROR)
            else:
                self.message_user(request,
                    (
                        "The security email is %"
                        ". Thanks!"
                    )
                    % security_email,
                )
        print("above make domain")

        if MAKE_DOMAIN in request.POST:
            print("in make domain")

            try:
                obj._get_or_create_domain()
            except Exception as err:
                self.message_user(request, err, messages.ERROR)
            else:
                self.message_user(request,
                    (
                        "Domain created with %"
                        ". Thanks!"
                    )
                    % obj.name,
                )
            return HttpResponseRedirect(".")
        return super().response_change(request, obj)
    # def response_change(self, request, obj):
    #     ACTION_BUTTON = "_get_security_email"

    #     if ACTION_BUTTON in request.POST:
    #         try:
    #             obj.security
    #         except Exception as err:
    #             self.message_user(request, err, messages.ERROR)
    #         else:
    #             self.message_user(
    #                 request,
    #                 (
    #                     "%s is in client hold. This domain is no longer accessible on"
    #                     " the public internet."
    #                 )
    #                 % obj.name,
    #             )
    #         return HttpResponseRedirect(".")

    #     return super().response_change(request, obj)


class ContactAdmin(ListHeaderAdmin):
    """Custom contact admin class to add search."""

    search_fields = ["email", "first_name", "last_name"]
    search_help_text = "Search by firstname, lastname or email."


class DomainApplicationAdmin(ListHeaderAdmin):

    """Customize the applications listing view."""

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


admin.site.register(models.User, MyUserAdmin)
admin.site.register(models.UserDomainRole, AuditedAdmin)
admin.site.register(models.Contact, ContactAdmin)
admin.site.register(models.DomainInvitation, AuditedAdmin)
admin.site.register(models.DomainInformation, AuditedAdmin)
admin.site.register(models.Domain, DomainAdmin)
admin.site.register(models.Host, MyHostAdmin)
admin.site.register(models.Nameserver, MyHostAdmin)
admin.site.register(models.Website, AuditedAdmin)
admin.site.register(models.PublicContact, AuditedAdmin)
admin.site.register(models.DomainApplication, DomainApplicationAdmin)
