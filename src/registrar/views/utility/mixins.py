"""Permissions-related mixin classes."""

from django.contrib.auth.mixins import PermissionRequiredMixin

from registrar.models import UserDomainRole


class PermissionsLoginMixin(PermissionRequiredMixin):

    """Mixin that redirects to login page if not logged in, otherwise 403."""

    def handle_no_permission(self):
        self.raise_exception = self.request.user.is_authenticated
        return super().handle_no_permission()


class DomainPermission(PermissionsLoginMixin):

    """Does the logged-in user have access to this domain?"""

    def has_permission(self):
        """Check if this user has access to this domain.

        The user is in self.request.user and the domain needs to be looked
        up from the domain's primary key in self.kwargs["pk"]
        """
        if not self.request.user.is_authenticated:
            return False

        # user needs to have a role on the domain
        try:
            role = UserDomainRole.objects.get(
                user=self.request.user, domain__id=self.kwargs["pk"]
            )
        except UserDomainRole.DoesNotExist:
            # can't find the role
            return False

        # if we need to check more about the nature of role, do it here.
        return True
