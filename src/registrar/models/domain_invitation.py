"""People are invited by email to administer domains."""

from django.contrib.auth import get_user_model
from django.db import models, IntegrityError

from django_fsm import FSMField, transition  # type: ignore

from .utility.time_stamped_model import TimeStampedModel
from .user_domain_role import UserDomainRole


class DomainInvitation(TimeStampedModel):
    SENT = "sent"
    RETRIEVED = "retrieved"

    email = models.EmailField(
        null=False,
        blank=False,
    )

    domain = models.ForeignKey(
        "registrar.Domain",
        on_delete=models.CASCADE,  # delete domain, then get rid of invitations
        null=False,
        related_name="invitations",
    )

    status = FSMField(
        choices=[
            (SENT, SENT),
            (RETRIEVED, RETRIEVED),
        ],
        default=SENT,
        protected=True,  # can't alter state except through transition methods!
    )

    def __str__(self):
        return f"Invitation for {self.email} on {self.domain} is {self.status}"

    @transition(field="status", source=SENT, target=RETRIEVED)
    def retrieve(self):
        """When an invitation is retrieved, create the corresponding permission."""

        # get a user with this email address
        User = get_user_model()
        try:
            user = User.objects.get(email=self.email)
        except User.DoesNotExist:
            # should not happen because a matching user should exist before
            # we retrieve this invitation
            raise RuntimeError(
                "Cannot find the user to retrieve this domain invitation."
            )

        # and create a role for that user on this domain
        try:
            UserDomainRole.objects.create(
                user=user, domain=self.domain, role=UserDomainRole.Roles.ADMIN
            )
        except IntegrityError:
            # should not happen because this user shouldn't retrieve this invitation
            # more than once.
            raise RuntimeError(
                "Invitation would create a role that already exists for this user."
            )
