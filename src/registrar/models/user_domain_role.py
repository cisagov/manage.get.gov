from django.db import models

from .utility.time_stamped_model import TimeStampedModel


class UserDomainRole(TimeStampedModel):
    """This is a linking table that connects a user with a role on a domain."""

    class Roles(models.TextChoices):
        """The possible roles are listed here.

        Implementation of the named roles for allowing particular operations happens
        elsewhere.
        """

        MANAGER = "manager"

    user = models.ForeignKey(
        "registrar.User",
        null=False,
        on_delete=models.CASCADE,  # when a user is deleted, permissions are too
        related_name="permissions",
    )

    domain = models.ForeignKey(
        "registrar.Domain",
        null=False,
        on_delete=models.CASCADE,  # when a domain is deleted, permissions are too
        related_name="permissions",
    )

    role = models.TextField(
        choices=Roles.choices,
        null=False,
        blank=False,
    )

    def __str__(self):
        return "User {} is {} on domain {}".format(self.user, self.role, self.domain)

    class Meta:
        constraints = [
            # a user can have only one role on a given domain, that is, there can
            # be only a single row with a certain (user, domain) pair.
            models.UniqueConstraint(fields=["user", "domain"], name="unique_user_domain_role")
        ]
