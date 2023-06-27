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


class DomainAdmin(AuditedAdmin):

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
    
    
class ContactAdmin(AuditedAdmin):
    
    """Custom contact admin class to add search."""

    search_fields = ["email", "first_name", "last_name"]
    search_help_text = "Search by firstname, lastname or email."


class DomainApplicationAdmin(AuditedAdmin):

    """Customize the applications listing view."""
    
    list_display = ["requested_domain", "status", "organization_type", "created_at", "submitter", "investigator"]  
    list_filter = ('status', "organization_type", "investigator")  
    search_fields = ["requested_domain__name", "submitter__email", "submitter__first_name", "submitter__last_name"]
    search_help_text = "Search by domain or submitter."
    fieldsets = [
        (None, {"fields": ["status", "investigator", "creator"]}),
        ("Type of organization", {"fields": ["organization_type", "federally_recognized_tribe", "state_recognized_tribe", "tribe_name", "federal_agency", "federal_type", "is_election_board", "type_of_work", "more_organization_information"]}),
        ("Organization name and mailing address", {"fields": ["organization_name", "address_line1", "address_line2", "city", "state_territory", "zipcode", "urbanization"]}),
        ("Authorizing official", {"fields": ["authorizing_official"]}),
        ("Current websites", {"fields": ["current_websites"]}),
        (".gov domain", {"fields": ["requested_domain", "alternative_domains"]}),
        ("Purpose of your domain", {"fields": ["purpose"]}),
        ("Your contact information", {"fields": ["submitter"]}),
        ("Other employees from your organization?", {"fields": ["other_contacts"]}),
        ("No other employees from your organization?", {"fields": ["no_other_contacts_rationale"]}),
        ("Anything else we should know?", {"fields": ["anything_else"]}),
        ("Requirements for operating .gov domains", {"fields": ["is_policy_acknowledged"]}),
    ]
    readonly_fields = ["creator", "type_of_work", "more_organization_information", "address_line1", "address_line2", "zipcode", "requested_domain", "alternative_domains", "purpose", "submitter", "no_other_contacts_rationale", "anything_else", "is_policy_acknowledged"]

    # Trigger action when a fieldset is changed
    def save_model(self, request, obj, form, change):
        if change:  # Check if the application is being edited
            # Get the original application from the database
            original_obj = models.DomainApplication.objects.get(pk=obj.pk)

            if (
                obj.status != original_obj.status
                and obj.status == models.DomainApplication.INVESTIGATING
            ):
                # This is a transition annotated method in model which will throw an
                # error if the condition is violated. To make this work, we need to
                # call it on the original object which has the right status value,
                # but pass the current object which contains the up-to-date data
                # for the email.
                original_obj.in_review(obj)

        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            # Superusers have full access, no fields are read-only
            return ()
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
