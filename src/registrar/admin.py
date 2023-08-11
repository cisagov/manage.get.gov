import logging
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
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


class MyUserAdmin(UserAdmin):

    """Custom user admin class to use our inlines."""

    inlines = [UserContactInline]


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
                elif obj.status == models.DomainApplication.INVESTIGATING:
                    original_obj.in_review(updated_domain_application=obj)
                elif obj.status == models.DomainApplication.APPROVED:
                    original_obj.approve(updated_domain_application=obj)
                elif obj.status == models.DomainApplication.WITHDRAWN:
                    original_obj.withdraw()
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
