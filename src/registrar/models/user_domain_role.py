from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError

from .utility.time_stamped_model import TimeStampedModel


class UserDomainRole(TimeStampedModel):
    """This is a linking table that connects a user with a role on a domain."""

    class Meta:
        constraints = [
            # a user can have only one role on a given domain, that is, there can
            # be only a single row with a certain (user, domain) pair.
            models.UniqueConstraint(fields=["user", "domain"], name="unique_user_domain_role"),
            # user can be NULL only when status is invited (e.g. cannot be null when accepted)
            models.CheckConstraint(
                check=Q(user__isnull=False) | Q(status="invited"),
                name="user_null_only_when_invited",
            ),
        ]

    class Roles(models.TextChoices):
        """The possible roles are listed here.

        Implementation of the named roles for allowing particular operations happens
        elsewhere.
        """

        MANAGER = "manager"

    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"

    user = models.ForeignKey(
        "registrar.User",
        null=True,
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

    # Invitation fields
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        null=True,
        help_text="Status of the invitation",
    )

    invited_by = models.ForeignKey(
        "registrar.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="domain_roles_invited",
        help_text="User who created the invitation",
    )

    invited_at = models.DateTimeField(null=True, blank=True)

    email = models.EmailField(null=True, blank=True)

    accepted_at = models.DateTimeField(null=True, blank=True)

    revoked_at = models.DateTimeField(null=True, blank=True)

    revocation_reason = models.TextField(null=True, blank=True)

    # End Invitation fields

    def __str__(self):
        return "User {} is {} on domain {}".format(self.user, self.role, self.domain)

    def clean(self):
        # Ensure user is present for any non-invited status
        super().clean()
        if self.status != self.Status.INVITED and self.user_id is None:
            raise ValidationError({"user": "User is required when status is not 'invited'."})
