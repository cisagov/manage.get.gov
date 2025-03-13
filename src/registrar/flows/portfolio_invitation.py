import logging
from registrar.models.portfolio_invitation import PortfolioInvitation
from django.contrib.auth import get_user_model
from viewflow import fsm

from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.user_portfolio_permission import UserPortfolioPermission


class PortfolioInvitationFlow(object):
    """
    Controls the "flow" between states of the Portfolio Invitation object
    Only pass PortfolioInvitation to this class
    """

    status = fsm.State(
        PortfolioInvitation.PortfolioInvitationStatus, default=PortfolioInvitation.PortfolioInvitationStatus.INVITED
    )

    def __init__(self, portfolio_invitation):
        self.portfolio_invitation = portfolio_invitation

    @status.setter()
    def _set_portfolio_invitation_status(self, value):
        self.portfolio_invitation.__dict__["status"] = value

    @status.getter()
    def _get_portfolio_invitation_status(self):
        return self.portfolio_invitation.status

    @status.transition(
        source=PortfolioInvitation.PortfolioInvitationStatus.INVITED,
        target=PortfolioInvitation.PortfolioInvitationStatus.RETRIEVED,
    )
    def retrieve(self):
        """When an invitation is retrieved, create the corresponding permission.

        Raises:
            RuntimeError if no matching user can be found.
        """

        # get a user with this email address
        User = get_user_model()
        try:
            user = User.objects.get(email=self.portfolio_invitation.email)
        except User.DoesNotExist:
            # should not happen because a matching user should exist before
            # we retrieve this invitation
            raise RuntimeError("Cannot find the user to retrieve this portfolio invitation.")

        # and create a role for that user on this portfolio
        user_portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
            portfolio=self.portfolio_invitation.portfolio, user=user
        )

        if self.portfolio_invitation.roles and len(self.portfolio_invitation.roles) > 0:
            user_portfolio_permission.roles = self.portfolio_invitation.roles

        if (
            self.portfolio_invitation.additional_permissions
            and len(self.portfolio_invitation.additional_permissions) > 0
        ):
            user_portfolio_permission.additional_permissions = self.portfolio_invitation.additional_permissions

        user_portfolio_permission.save()
