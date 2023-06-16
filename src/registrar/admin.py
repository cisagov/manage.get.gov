from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.contenttypes.models import ContentType
from django.http.response import HttpResponseRedirect
from django.urls import reverse

from . import models


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


admin.site.register(models.User, MyUserAdmin)
admin.site.register(models.UserDomainRole, AuditedAdmin)
admin.site.register(models.Contact, AuditedAdmin)
admin.site.register(models.DomainInvitation, AuditedAdmin)
admin.site.register(models.DomainApplication, AuditedAdmin)
admin.site.register(models.DomainInformation, AuditedAdmin)
admin.site.register(models.Domain, DomainAdmin)
admin.site.register(models.Host, MyHostAdmin)
admin.site.register(models.Nameserver, MyHostAdmin)
admin.site.register(models.Website, AuditedAdmin)
