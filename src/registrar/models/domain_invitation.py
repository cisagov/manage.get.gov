"""People are invited by email to administer domains."""

import logging

from django.contrib.auth import get_user_model
from django.db import models

#from django_fsm import FSMField, transition  # type: ignore
from viewflow import fsm
from .utility.time_stamped_model import TimeStampedModel
from .user_domain_role import UserDomainRole
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class DomainInvitation(TimeStampedModel):
    class Meta:
        """Contains meta information about this class"""

        indexes = [
            models.Index(fields=["status"]),
        ]

    # Constants for status field
    class DomainInvitationStatus(models.TextChoices):
        INVITED = "invited", "Invited"
        RETRIEVED = "retrieved", "Retrieved"
        CANCELED = "canceled", "Canceled"

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

    status = models.CharField(
        choices=DomainInvitationStatus.choices,
        default=DomainInvitationStatus.INVITED,
    )

    def __str__(self):
        return f"Invitation for {self.email} on {self.domain} is {self.status}"
    
    def _is_being_created(self):
        """returns true if the object is new and hasn't been saved in the db"""
        #_state exists on object after initialization
        # `adding` is set to True by django
        # only when the object hasn't been saved to the db
        #django automagically changes this to false after db-save
        return getattr(self, "_state", None) and self._state.adding
    
    def __setattr__(self, name, value):
        """ Overrides the setter ('=' operator) with custom logic """

        if name == "status" and not self._is_being_created() :       
            raise ValidationError("Direct changes to 'status' are not allowed.")
        super().__setattr__(name, value)
    # @transition(field="status", source=DomainInvitationStatus.INVITED, target=DomainInvitationStatus.RETRIEVED)
    # def retrieve(self):
    #     """When an invitation is retrieved, create the corresponding permission.

    #     Raises:
    #         RuntimeError if no matching user can be found.
    #     """

    #     # get a user with this email address
    #     User = get_user_model()
    #     try:
    #         user = User.objects.get(email=self.email)
    #     except User.DoesNotExist:
    #         # should not happen because a matching user should exist before
    #         # we retrieve this invitation
    #         raise RuntimeError("Cannot find the user to retrieve this domain invitation.")

    #     # and create a role for that user on this domain
    #     _, created = UserDomainRole.objects.get_or_create(
    #         user=user, domain=self.domain, role=UserDomainRole.Roles.MANAGER
    #     )
    #     if not created:
    #         # something strange happened and this role already existed when
    #         # the invitation was retrieved. Log that this occurred.
    #         logger.warn("Invitation %s was retrieved for a role that already exists.", self)

    # @transition(field="status", source=DomainInvitationStatus.INVITED, target=DomainInvitationStatus.CANCELED)
    # def cancel_invitation(self):
    #     """When an invitation is canceled, change the status to canceled"""
    #     pass

    # @transition(field="status", source=DomainInvitationStatus.CANCELED, target=DomainInvitationStatus.INVITED)
    # def update_cancellation_status(self):
    #     """When an invitation is canceled but reinvited, update the status to invited"""
    #     pass


class DomainInvitationFlow(object):

    status = fsm.State(DomainInvitation.DomainInvitationStatus, default=DomainInvitation.DomainInvitationStatus.INVITED)

    def __init__(self, domain_invitation):
        self.domain_invitation = domain_invitation

    @status.setter()
    def _set_domain_invitation_status(self, value):
        self.domain_invitation.__dict__["status"]=value


    @status.getter()
    def _get_domain_invitation_status(self):
        return self.domain_invitation.status
    
    @status.transition(source=DomainInvitation.DomainInvitationStatus.INVITED, target=DomainInvitation.DomainInvitationStatus.RETRIEVED)
    def retrieve(self):
        """When an invitation is retrieved, create the corresponding permission.

        Raises:
            RuntimeError if no matching user can be found.
        """

        # get a user with this email address
        User = get_user_model()
        try:
            user = User.objects.get(email=self.domain_invitation.email)
        except User.DoesNotExist:
            # should not happen because a matching user should exist before
            # we retrieve this invitation
            raise RuntimeError("Cannot find the user to retrieve this domain invitation.")

        # and create a role for that user on this domain
        _, created = UserDomainRole.objects.get_or_create(
            user=user, domain=self.domain_invitation.domain, role=UserDomainRole.Roles.MANAGER
        )
        if not created:
            # something strange happened and this role already existed when
            # the invitation was retrieved. Log that this occurred.
            logger.warn("Invitation %s was retrieved for a role that already exists.", self.domain_invitation)

    @status.transition(source=DomainInvitation.DomainInvitationStatus.INVITED, target=DomainInvitation.DomainInvitationStatus.CANCELED)
    def cancel_invitation(self):
        """When an invitation is canceled, change the status to canceled"""
        pass

    @status.transition(source=DomainInvitation.DomainInvitationStatus.CANCELED, target=DomainInvitation.DomainInvitationStatus.INVITED)
    def update_cancellation_status(self):
        """When an invitation is canceled but reinvited, update the status to invited"""
        pass
