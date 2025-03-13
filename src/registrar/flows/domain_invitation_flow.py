from registrar.models import DomainInvitation, UserDomainRole
from viewflow import fsm
import logging
from django.contrib.auth import get_user_model


logger = logging.getLogger(__name__)

class DomainInvitationFlow(object):
    """
    Controls the "flow" between states of the Domain Invitation object
    Only pass DomainInvitation to this class
    """
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
            logger.warning("Invitation %s was retrieved for a role that already exists.", self.domain_invitation)

    @status.transition(source=DomainInvitation.DomainInvitationStatus.INVITED, target=DomainInvitation.DomainInvitationStatus.CANCELED)
    def cancel_invitation(self):
        """When an invitation is canceled, change the status to canceled"""
        pass

    @status.transition(source=DomainInvitation.DomainInvitationStatus.CANCELED, target=DomainInvitation.DomainInvitationStatus.INVITED)
    def update_cancellation_status(self):
        """When an invitation is canceled but reinvited, update the status to invited"""
        pass
