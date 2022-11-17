from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.contenttypes.models import ContentType
from django.http.response import HttpResponseRedirect
from django.urls import reverse

from .models import User, UserProfile, DomainApplication, Website


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


class UserProfileInline(admin.StackedInline):

    """Edit a user's profile on the user page."""

    model = UserProfile


class MyUserAdmin(UserAdmin):

    """Custom user admin class to use our inlines."""

    inlines = [UserProfileInline]


admin.site.register(User, MyUserAdmin)
admin.site.register(DomainApplication, AuditedAdmin)
admin.site.register(Website, AuditedAdmin)
