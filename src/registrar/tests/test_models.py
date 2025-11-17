from django.forms import ValidationError
from django.test import TestCase
from unittest.mock import patch
from unittest.mock import Mock
from django.test import RequestFactory
from registrar.views.domain_request import DomainRequestWizard
from registrar.models import (
    Contact,
    DomainRequest,
    DomainInformation,
    User,
    Website,
    Domain,
    DraftDomain,
    DomainInvitation,
    UserDomainRole,
    FederalAgency,
    UserPortfolioPermission,
    AllowedEmail,
)
import boto3_mocking
from registrar.models.portfolio import Portfolio
from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.transition_domain import TransitionDomain
from registrar.models.utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices
from registrar.models.verified_by_staff import VerifiedByStaff  # type: ignore

from .common import (
    MockSESClient,
    completed_domain_request,
    create_superuser,
    create_test_user,
)
from waffle.testutils import override_flag

from api.tests.common import less_console_noise_decorator


class TestDomainInformation(TestCase):
    """Test the DomainInformation model, when approved or otherwise"""

    def setUp(self):
        super().setUp()
        self.mock_client = MockSESClient()

    def tearDown(self):
        super().tearDown()
        self.mock_client.EMAILS_SENT.clear()
        Domain.objects.all().delete()
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        User.objects.all().delete()
        DraftDomain.objects.all().delete()

    @boto3_mocking.patching
    @less_console_noise_decorator
    def test_approval_creates_info(self):
        draft_domain, _ = DraftDomain.objects.get_or_create(name="igorville.gov")
        user, _ = User.objects.get_or_create()
        investigator, _ = User.objects.get_or_create(username="frenchtoast", is_staff=True)
        domain_request = DomainRequest.objects.create(
            requester=user, requested_domain=draft_domain, notes="test notes", investigator=investigator
        )

        with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
            # skip using the submit method
            domain_request.status = DomainRequest.DomainRequestStatus.IN_REVIEW
            domain_request.approve()

            # should be an information present for this domain
            domain = Domain.objects.get(name="igorville.gov")
            domain_information = DomainInformation.objects.filter(domain=domain)
            self.assertTrue(domain_information.exists())

            # Test that both objects are what we expect
            current_domain_information = domain_information.get().__dict__
            expected_domain_information = DomainInformation(
                requester=user,
                domain=domain,
                notes="test notes",
                domain_request=domain_request,
                federal_agency=FederalAgency.objects.get(agency="Non-Federal Agency"),
            ).__dict__

            # Test the two records for consistency
            self.assertEqual(self.clean_dict(current_domain_information), self.clean_dict(expected_domain_information))

    def clean_dict(self, dict_obj):
        """Cleans dynamic fields in a dictionary"""
        bad_fields = ["_state", "created_at", "id", "updated_at"]
        return {k: v for k, v in dict_obj.items() if k not in bad_fields}


class TestDomainInvitations(TestCase):
    """Test the retrieval of domain invitations."""

    @less_console_noise_decorator
    def setUp(self):
        self.domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        self.email = "mayor@igorville.gov"
        self.invitation, _ = DomainInvitation.objects.get_or_create(email=self.email, domain=self.domain)
        self.user, _ = User.objects.get_or_create(email=self.email)

    def tearDown(self):
        super().tearDown()
        # clean out the roles each time
        UserDomainRole.objects.all().delete()
        self.domain.delete()
        self.invitation.delete()
        User.objects.all().delete()

    @less_console_noise_decorator
    def test_retrieval_creates_role(self):
        self.invitation.retrieve()
        self.assertTrue(UserDomainRole.objects.get(user=self.user, domain=self.domain))

    @less_console_noise_decorator
    def test_retrieve_missing_user_error(self):
        # get rid of matching users
        User.objects.filter(email=self.email).delete()
        with self.assertRaises(RuntimeError):
            self.invitation.retrieve()

    @less_console_noise_decorator
    def test_retrieve_existing_role_no_error(self):
        # make the overlapping role
        UserDomainRole.objects.get_or_create(user=self.user, domain=self.domain, role=UserDomainRole.Roles.MANAGER)
        # this is not an error but does produce a console warning
        self.invitation.retrieve()
        self.assertEqual(self.invitation.status, DomainInvitation.DomainInvitationStatus.RETRIEVED)

    @less_console_noise_decorator
    def test_retrieve_on_each_login(self):
        """A user's authenticate on_each_login callback retrieves their invitations."""
        self.user.on_each_login()
        self.assertTrue(UserDomainRole.objects.get(user=self.user, domain=self.domain))

    @less_console_noise_decorator
    def test_clean_validates_retrieved_invitation_has_role(self):
        """Test that clean() validates retrieved invitations have corresponding UserDomainRole."""
        from django.core.exceptions import ValidationError

        # Retrieve the invitation (this creates the role)
        self.invitation.retrieve()
        self.invitation.save()
        # This should pass validation since the role exists
        self.invitation.clean()

        # Now delete the role - this should cause validation to fail
        UserDomainRole.objects.filter(user=self.user, domain=self.domain).delete()
        with self.assertRaises(ValidationError) as context:
            self.invitation.clean()

        # Check that the error message contains the expected text (non-field error)
        error_message = str(context.exception)
        self.assertIn("no corresponding UserDomainRole", error_message)

    @less_console_noise_decorator
    def test_clean_validates_retrieved_invitation_user_exists(self):
        """Test that clean() validates retrieved invitations have a corresponding user."""
        from django.core.exceptions import ValidationError

        # Retrieve the invitation (this creates the role)
        self.invitation.retrieve()
        self.invitation.save()

        # Now delete the role - this should cause validation to fail
        self.user.delete()
        with self.assertRaises(ValidationError) as context:
            self.invitation.clean()

        # Check that the error message contains the expected text (non-field error)
        error_message = str(context.exception)
        self.assertIn("user with email", error_message)


class TestPortfolioInvitations(TestCase):
    """Test the retrieval of portfolio invitations."""

    @less_console_noise_decorator
    def setUp(self):
        self.email = "mayor@igorville.gov"
        self.email2 = "requester@igorville.gov"
        self.user, _ = User.objects.get_or_create(email=self.email)
        self.user2, _ = User.objects.get_or_create(email=self.email2, username="requester")
        self.portfolio, _ = Portfolio.objects.get_or_create(requester=self.user2, organization_name="Hotel California")
        self.portfolio_role_base = UserPortfolioRoleChoices.ORGANIZATION_MEMBER
        self.portfolio_role_admin = UserPortfolioRoleChoices.ORGANIZATION_ADMIN
        self.portfolio_permission_1 = UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS
        self.portfolio_permission_2 = UserPortfolioPermissionChoices.EDIT_REQUESTS
        self.invitation, _ = PortfolioInvitation.objects.get_or_create(
            email=self.email,
            portfolio=self.portfolio,
            roles=[self.portfolio_role_base, self.portfolio_role_admin],
            additional_permissions=[self.portfolio_permission_1, self.portfolio_permission_2],
        )
        self.superuser = create_superuser()

    def tearDown(self):
        super().tearDown()
        DomainInvitation.objects.all().delete()
        DomainInformation.objects.all().delete()
        Domain.objects.all().delete()
        UserPortfolioPermission.objects.all().delete()
        UserDomainRole.objects.all().delete()
        Portfolio.objects.all().delete()
        PortfolioInvitation.objects.all().delete()
        User.objects.all().delete()

    @less_console_noise_decorator
    def test_retrieval(self):
        portfolio_role_exists = UserPortfolioPermission.objects.filter(
            user=self.user, portfolio=self.portfolio
        ).exists()
        self.assertFalse(portfolio_role_exists)
        self.invitation.retrieve()
        self.user.refresh_from_db()
        created_role = UserPortfolioPermission.objects.get(user=self.user, portfolio=self.portfolio)
        self.assertEqual(created_role.portfolio.organization_name, "Hotel California")
        self.assertEqual(created_role.roles, [self.portfolio_role_base, self.portfolio_role_admin])
        self.assertEqual(
            created_role.additional_permissions, [self.portfolio_permission_1, self.portfolio_permission_2]
        )
        self.assertEqual(self.invitation.status, PortfolioInvitation.PortfolioInvitationStatus.RETRIEVED)

    @less_console_noise_decorator
    def test_retrieve_missing_user_error(self):
        # get rid of matching users
        User.objects.filter(email=self.email).delete()
        with self.assertRaises(RuntimeError):
            self.invitation.retrieve()

    @less_console_noise_decorator
    def test_retrieve_user_already_member_error(self):
        portfolio_role_exists = UserPortfolioPermission.objects.filter(
            user=self.user, portfolio=self.portfolio
        ).exists()
        self.assertFalse(portfolio_role_exists)
        portfolio_role, _ = UserPortfolioPermission.objects.get_or_create(user=self.user, portfolio=self.portfolio)
        self.assertEqual(portfolio_role.portfolio.organization_name, "Hotel California")
        self.user.check_portfolio_invitations_on_login()
        self.user.refresh_from_db()

        roles = UserPortfolioPermission.objects.filter(user=self.user)
        self.assertEqual(len(roles), 1)
        self.assertEqual(self.invitation.status, PortfolioInvitation.PortfolioInvitationStatus.INVITED)

    @less_console_noise_decorator
    def test_retrieve_user_multiple_invitations(self):
        """Retrieve user portfolio invitations when there are multiple and multiple_options flag true."""
        # create a 2nd portfolio and a 2nd portfolio invitation to self.user
        portfolio2, _ = Portfolio.objects.get_or_create(requester=self.user2, organization_name="Take It Easy")
        PortfolioInvitation.objects.get_or_create(
            email=self.email,
            portfolio=portfolio2,
            roles=[self.portfolio_role_base, self.portfolio_role_admin],
            additional_permissions=[self.portfolio_permission_1, self.portfolio_permission_2],
        )
        with override_flag("multiple_portfolios", active=True):
            self.user.check_portfolio_invitations_on_login()
            self.user.refresh_from_db()
            roles = UserPortfolioPermission.objects.filter(user=self.user)
            self.assertEqual(len(roles), 2)
            updated_invitation1, _ = PortfolioInvitation.objects.get_or_create(
                email=self.email, portfolio=self.portfolio
            )
            self.assertEqual(updated_invitation1.status, PortfolioInvitation.PortfolioInvitationStatus.RETRIEVED)
            updated_invitation2, _ = PortfolioInvitation.objects.get_or_create(email=self.email, portfolio=portfolio2)
            self.assertEqual(updated_invitation2.status, PortfolioInvitation.PortfolioInvitationStatus.RETRIEVED)

    @less_console_noise_decorator
    def test_retrieve_user_multiple_invitations_when_multiple_portfolios_inactive(self):
        """Attempt to retrieve user portfolio invitations when there are multiple
        but multiple_portfolios flag set to False"""
        # create a 2nd portfolio and a 2nd portfolio invitation to self.user
        portfolio2, _ = Portfolio.objects.get_or_create(requester=self.user2, organization_name="Take It Easy")
        PortfolioInvitation.objects.get_or_create(
            email=self.email,
            portfolio=portfolio2,
            roles=[self.portfolio_role_base, self.portfolio_role_admin],
            additional_permissions=[self.portfolio_permission_1, self.portfolio_permission_2],
        )
        self.user.check_portfolio_invitations_on_login()
        self.user.refresh_from_db()
        roles = UserPortfolioPermission.objects.filter(user=self.user)
        self.assertEqual(len(roles), 1)
        updated_invitation1, _ = PortfolioInvitation.objects.get_or_create(email=self.email, portfolio=self.portfolio)
        self.assertEqual(updated_invitation1.status, PortfolioInvitation.PortfolioInvitationStatus.RETRIEVED)
        updated_invitation2, _ = PortfolioInvitation.objects.get_or_create(email=self.email, portfolio=portfolio2)
        self.assertEqual(updated_invitation2.status, PortfolioInvitation.PortfolioInvitationStatus.INVITED)

    @less_console_noise_decorator
    def test_get_managed_domains_count(self):
        """Test that the correct number of domains, which are associated with the portfolio and
        have invited the email of the portfolio invitation, are returned."""
        # Add three domains, one which is in the portfolio and email is invited to,
        # one which is in the portfolio and email is not invited to,
        # and one which is email is invited to and not in the portfolio.
        # Arrange
        # domain_in_portfolio should not be included in the count
        domain_in_portfolio, _ = Domain.objects.get_or_create(name="domain_in_portfolio.gov", state=Domain.State.READY)
        DomainInformation.objects.get_or_create(
            requester=self.user, domain=domain_in_portfolio, portfolio=self.portfolio
        )
        # domain_in_portfolio_and_invited should be included in the count
        domain_in_portfolio_and_invited, _ = Domain.objects.get_or_create(
            name="domain_in_portfolio_and_invited.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(
            requester=self.user, domain=domain_in_portfolio_and_invited, portfolio=self.portfolio
        )
        DomainInvitation.objects.get_or_create(email=self.email, domain=domain_in_portfolio_and_invited)
        # domain_invited should not be included in the count
        domain_invited, _ = Domain.objects.get_or_create(name="domain_invited.gov", state=Domain.State.READY)
        DomainInformation.objects.get_or_create(requester=self.user, domain=domain_invited)
        DomainInvitation.objects.get_or_create(email=self.email, domain=domain_invited)

        # Assert
        self.assertEqual(self.invitation.get_managed_domains_count(), 1)

    @less_console_noise_decorator
    def test_get_portfolio_permissions(self):
        """Test that get_portfolio_permissions returns the expected list of permissions,
        based on the roles and permissions assigned to the invitation."""
        # Arrange
        test_permission_list = set()
        # add the arrays that are defined in UserPortfolioPermission for member and admin
        test_permission_list.update(
            UserPortfolioPermission.PORTFOLIO_ROLE_PERMISSIONS.get(UserPortfolioRoleChoices.ORGANIZATION_MEMBER, [])
        )
        test_permission_list.update(
            UserPortfolioPermission.PORTFOLIO_ROLE_PERMISSIONS.get(UserPortfolioRoleChoices.ORGANIZATION_ADMIN, [])
        )
        # add the permissions that are added to the invitation as additional_permissions
        test_permission_list.update([self.portfolio_permission_1, self.portfolio_permission_2])
        perm_list = list(test_permission_list)
        # Verify
        self.assertEquals(self.invitation.get_portfolio_permissions(), perm_list)

    @less_console_noise_decorator
    @override_flag("multiple_portfolios", active=False)
    def test_clean_multiple_portfolios_inactive(self):
        """Tests that users cannot have multiple portfolios or invitations when flag is inactive"""
        # Create the first portfolio permission
        UserPortfolioPermission.objects.create(
            user=self.superuser, portfolio=self.portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )

        # Test a second portfolio permission object (should fail)
        second_portfolio = Portfolio.objects.create(organization_name="Second Portfolio", requester=self.superuser)
        second_permission = UserPortfolioPermission(
            user=self.superuser, portfolio=second_portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )

        with self.assertRaises(ValidationError) as err:
            second_permission.clean()
        self.assertIn("users cannot be assigned to multiple portfolios", str(err.exception))

        # Test that adding a new portfolio invitation also fails
        third_portfolio = Portfolio.objects.create(organization_name="Third Portfolio", requester=self.superuser)
        invitation = PortfolioInvitation(
            email=self.superuser.email, portfolio=third_portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )

        with self.assertRaises(ValidationError) as err:
            invitation.clean()
        self.assertIn("users cannot be assigned to multiple portfolios", str(err.exception))

    @less_console_noise_decorator
    @override_flag("multiple_portfolios", active=True)
    def test_clean_multiple_portfolios_active(self):
        """Tests that users can have multiple portfolios and invitations when flag is active"""
        # Create first portfolio permission
        UserPortfolioPermission.objects.create(
            user=self.superuser, portfolio=self.portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )

        # Second portfolio permission should succeed
        second_portfolio = Portfolio.objects.create(organization_name="Second Portfolio", requester=self.superuser)
        second_permission = UserPortfolioPermission(
            user=self.superuser, portfolio=second_portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )
        second_permission.clean()
        second_permission.save()

        # Verify both permissions exist
        user_permissions = UserPortfolioPermission.objects.filter(user=self.superuser)
        self.assertEqual(user_permissions.count(), 2)

        # Portfolio invitation should also succeed
        third_portfolio = Portfolio.objects.create(organization_name="Third Portfolio", requester=self.superuser)
        invitation = PortfolioInvitation(
            email=self.superuser.email, portfolio=third_portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )
        invitation.clean()
        invitation.save()

        # Verify invitation exists
        self.assertTrue(
            PortfolioInvitation.objects.filter(
                email=self.superuser.email,
                portfolio=third_portfolio,
            ).exists()
        )

    @less_console_noise_decorator
    def test_clean_portfolio_invitation(self):
        """Tests validation of portfolio invitation permissions"""

        # Test validation fails when portfolio missing but permissions present
        invitation = PortfolioInvitation(email="test@example.com", roles=["organization_admin"], portfolio=None)
        with self.assertRaises(ValidationError) as err:
            invitation.clean()
            self.assertEqual(
                str(err.exception),
                "When portfolio roles or additional permissions are assigned, portfolio is required.",
            )

        # Test validation fails when portfolio present but no permissions
        invitation = PortfolioInvitation(email="test@example.com", roles=None, portfolio=self.portfolio)
        with self.assertLogs("registrar.models.utility.portfolio_helper", level="INFO") as cleaned_msg:
            invitation.clean()

        self.assertIn(
            "User didn't provide both a valid email address and a role for the member",
            "".join(cleaned_msg.output),
        )

        # Test validation fails with forbidden permissions
        forbidden_member_roles = UserPortfolioPermission.FORBIDDEN_PORTFOLIO_ROLE_PERMISSIONS.get(
            UserPortfolioRoleChoices.ORGANIZATION_MEMBER
        )
        invitation = PortfolioInvitation(
            email="test@example.com",
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            additional_permissions=forbidden_member_roles,
            portfolio=self.portfolio,
        )
        with self.assertRaises(ValidationError) as err:
            invitation.clean()
            self.assertEqual(
                str(err.exception),
                "These permissions cannot be assigned to Member: "
                "<View all domains and domain reports, Create and edit members, View members>",
            )

    @less_console_noise_decorator
    @override_flag("multiple_portfolios", active=False)
    def test_clean_user_portfolio_permission_multiple_portfolios_flag_off_and_duplicate_permission(self):
        """MISSING TEST: Test validation of multiple_portfolios flag.
        Scenario 1: Flag is inactive, and the user has existing portfolio permissions

        NOTE: Refer to the same test under TestUserPortfolioPermission"""

        pass

    @less_console_noise_decorator
    @override_flag("multiple_portfolios", active=False)
    def test_clean_user_portfolio_permission_multiple_portfolios_flag_off_and_existing_invitation(self):
        """MISSING TEST: Test validation of multiple_portfolios flag.
        Scenario 2: Flag is inactive, and the user has existing portfolio invitation to another portfolio

        NOTE: Refer to the same test under TestUserPortfolioPermission"""

        pass

    @less_console_noise_decorator
    @override_flag("multiple_portfolios", active=True)
    def test_clean_user_portfolio_permission_multiple_portfolios_flag_on_and_duplicate_permission(self):
        """MISSING TEST: Test validation of multiple_portfolios flag.
        Scenario 3: Flag is active, and the user has existing portfolio invitation

        NOTE: Refer to the same test under TestUserPortfolioPermission"""

        pass

    @less_console_noise_decorator
    @override_flag("multiple_portfolios", active=True)
    def test_clean_user_portfolio_permission_multiple_portfolios_flag_on_and_existing_invitation(self):
        """MISSING TEST: Test validation of multiple_portfolios flag.
        Scenario 4: Flag is active, and the user has existing portfolio invitation to another portfolio

        NOTE: Refer to the same test under TestUserPortfolioPermission"""

        pass

    @less_console_noise_decorator
    def test_delete_portfolio_invitation_deletes_portfolio_domain_invitations(self):
        """Deleting a portfolio invitation causes domain invitations for the same email on the same
        portfolio to be canceled."""

        email_with_no_user = "email-with-no-user@email.gov"

        domain_in_portfolio_1, _ = Domain.objects.get_or_create(
            name="domain_in_portfolio_1.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(
            requester=self.user, domain=domain_in_portfolio_1, portfolio=self.portfolio
        )
        invite_1, _ = DomainInvitation.objects.get_or_create(email=email_with_no_user, domain=domain_in_portfolio_1)

        domain_in_portfolio_2, _ = Domain.objects.get_or_create(
            name="domain_in_portfolio_and_invited_2.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(
            requester=self.user, domain=domain_in_portfolio_2, portfolio=self.portfolio
        )
        invite_2, _ = DomainInvitation.objects.get_or_create(email=email_with_no_user, domain=domain_in_portfolio_2)

        domain_not_in_portfolio, _ = Domain.objects.get_or_create(
            name="domain_not_in_portfolio.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(requester=self.user, domain=domain_not_in_portfolio)
        invite_3, _ = DomainInvitation.objects.get_or_create(email=email_with_no_user, domain=domain_not_in_portfolio)

        invitation_of_email_with_no_user, _ = PortfolioInvitation.objects.get_or_create(
            email=email_with_no_user,
            portfolio=self.portfolio,
            roles=[self.portfolio_role_base, self.portfolio_role_admin],
            additional_permissions=[self.portfolio_permission_1, self.portfolio_permission_2],
        )

        # The domain invitations start off as INVITED
        self.assertEqual(invite_1.status, DomainInvitation.DomainInvitationStatus.INVITED)
        self.assertEqual(invite_2.status, DomainInvitation.DomainInvitationStatus.INVITED)
        self.assertEqual(invite_3.status, DomainInvitation.DomainInvitationStatus.INVITED)

        # Delete member (invite)
        invitation_of_email_with_no_user.delete()

        # Reload the objects from the database
        invite_1 = DomainInvitation.objects.get(pk=invite_1.pk)
        invite_2 = DomainInvitation.objects.get(pk=invite_2.pk)
        invite_3 = DomainInvitation.objects.get(pk=invite_3.pk)

        # The domain invitations to the portfolio domains have been canceled
        self.assertEqual(invite_1.status, DomainInvitation.DomainInvitationStatus.CANCELED)
        self.assertEqual(invite_2.status, DomainInvitation.DomainInvitationStatus.CANCELED)

        # Invite 3 is unaffected
        self.assertEqual(invite_3.status, DomainInvitation.DomainInvitationStatus.INVITED)

    @less_console_noise_decorator
    def test_deleting_a_retrieved_invitation_has_no_side_effects(self):
        """Deleting a retrieved portfolio invitation causes no side effects."""

        domain_in_portfolio_1, _ = Domain.objects.get_or_create(
            name="domain_in_portfolio_1.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(
            requester=self.user, domain=domain_in_portfolio_1, portfolio=self.portfolio
        )
        invite_1, _ = DomainInvitation.objects.get_or_create(email=self.email, domain=domain_in_portfolio_1)

        domain_in_portfolio_2, _ = Domain.objects.get_or_create(
            name="domain_in_portfolio_and_invited_2.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(
            requester=self.user, domain=domain_in_portfolio_2, portfolio=self.portfolio
        )
        invite_2, _ = DomainInvitation.objects.get_or_create(email=self.email, domain=domain_in_portfolio_2)

        domain_in_portfolio_3, _ = Domain.objects.get_or_create(
            name="domain_in_portfolio_3.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(
            requester=self.user, domain=domain_in_portfolio_3, portfolio=self.portfolio
        )
        UserDomainRole.objects.get_or_create(
            user=self.user, domain=domain_in_portfolio_3, role=UserDomainRole.Roles.MANAGER
        )

        domain_in_portfolio_4, _ = Domain.objects.get_or_create(
            name="domain_in_portfolio_and_invited_4.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(
            requester=self.user, domain=domain_in_portfolio_4, portfolio=self.portfolio
        )
        UserDomainRole.objects.get_or_create(
            user=self.user, domain=domain_in_portfolio_4, role=UserDomainRole.Roles.MANAGER
        )

        domain_not_in_portfolio_1, _ = Domain.objects.get_or_create(
            name="domain_not_in_portfolio.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(requester=self.user, domain=domain_not_in_portfolio_1)
        invite_3, _ = DomainInvitation.objects.get_or_create(email=self.email, domain=domain_not_in_portfolio_1)

        domain_not_in_portfolio_2, _ = Domain.objects.get_or_create(
            name="domain_not_in_portfolio_2.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(requester=self.user, domain=domain_not_in_portfolio_2)
        UserDomainRole.objects.get_or_create(
            user=self.user, domain=domain_not_in_portfolio_2, role=UserDomainRole.Roles.MANAGER
        )

        # The domain invitations start off as INVITED
        self.assertEqual(invite_1.status, DomainInvitation.DomainInvitationStatus.INVITED)
        self.assertEqual(invite_2.status, DomainInvitation.DomainInvitationStatus.INVITED)
        self.assertEqual(invite_3.status, DomainInvitation.DomainInvitationStatus.INVITED)

        # The user domain roles exist
        self.assertTrue(
            UserDomainRole.objects.filter(
                user=self.user,
                domain=domain_in_portfolio_3,
            ).exists()
        )
        self.assertTrue(
            UserDomainRole.objects.filter(
                user=self.user,
                domain=domain_in_portfolio_4,
            ).exists()
        )
        self.assertTrue(
            UserDomainRole.objects.filter(
                user=self.user,
                domain=domain_not_in_portfolio_2,
            ).exists()
        )

        # retrieve the invitation
        self.invitation.retrieve()
        self.invitation.save()

        # Delete member (invite)
        self.invitation.delete()

        # Reload the objects from the database
        invite_1 = DomainInvitation.objects.get(pk=invite_1.pk)
        invite_2 = DomainInvitation.objects.get(pk=invite_2.pk)
        invite_3 = DomainInvitation.objects.get(pk=invite_3.pk)

        # Test that no side effects have been triggered
        self.assertEqual(invite_1.status, DomainInvitation.DomainInvitationStatus.INVITED)
        self.assertEqual(invite_2.status, DomainInvitation.DomainInvitationStatus.INVITED)
        self.assertEqual(invite_3.status, DomainInvitation.DomainInvitationStatus.INVITED)
        self.assertTrue(
            UserDomainRole.objects.filter(
                user=self.user,
                domain=domain_in_portfolio_3,
            ).exists()
        )
        self.assertTrue(
            UserDomainRole.objects.filter(
                user=self.user,
                domain=domain_in_portfolio_4,
            ).exists()
        )
        self.assertTrue(
            UserDomainRole.objects.filter(
                user=self.user,
                domain=domain_not_in_portfolio_2,
            ).exists()
        )

    @less_console_noise_decorator
    def test_delete_portfolio_invitation_deletes_user_domain_roles(self):
        """Deleting a portfolio invitation causes domain invitations for the same email on the same
        portfolio to be canceled, also deletes any exiting user domain roles on the portfolio for the
        user if the user exists."""

        domain_in_portfolio_1, _ = Domain.objects.get_or_create(
            name="domain_in_portfolio_1.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(
            requester=self.user, domain=domain_in_portfolio_1, portfolio=self.portfolio
        )
        invite_1, _ = DomainInvitation.objects.get_or_create(email=self.email, domain=domain_in_portfolio_1)

        domain_in_portfolio_2, _ = Domain.objects.get_or_create(
            name="domain_in_portfolio_and_invited_2.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(
            requester=self.user, domain=domain_in_portfolio_2, portfolio=self.portfolio
        )
        invite_2, _ = DomainInvitation.objects.get_or_create(email=self.email, domain=domain_in_portfolio_2)

        domain_in_portfolio_3, _ = Domain.objects.get_or_create(
            name="domain_in_portfolio_3.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(
            requester=self.user, domain=domain_in_portfolio_3, portfolio=self.portfolio
        )
        UserDomainRole.objects.get_or_create(
            user=self.user, domain=domain_in_portfolio_3, role=UserDomainRole.Roles.MANAGER
        )

        domain_in_portfolio_4, _ = Domain.objects.get_or_create(
            name="domain_in_portfolio_and_invited_4.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(
            requester=self.user, domain=domain_in_portfolio_4, portfolio=self.portfolio
        )
        UserDomainRole.objects.get_or_create(
            user=self.user, domain=domain_in_portfolio_4, role=UserDomainRole.Roles.MANAGER
        )

        domain_not_in_portfolio_1, _ = Domain.objects.get_or_create(
            name="domain_not_in_portfolio.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(requester=self.user, domain=domain_not_in_portfolio_1)
        invite_3, _ = DomainInvitation.objects.get_or_create(email=self.email, domain=domain_not_in_portfolio_1)

        domain_not_in_portfolio_2, _ = Domain.objects.get_or_create(
            name="domain_not_in_portfolio_2.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(requester=self.user, domain=domain_not_in_portfolio_2)
        UserDomainRole.objects.get_or_create(
            user=self.user, domain=domain_not_in_portfolio_2, role=UserDomainRole.Roles.MANAGER
        )

        # The domain invitations start off as INVITED
        self.assertEqual(invite_1.status, DomainInvitation.DomainInvitationStatus.INVITED)
        self.assertEqual(invite_2.status, DomainInvitation.DomainInvitationStatus.INVITED)
        self.assertEqual(invite_3.status, DomainInvitation.DomainInvitationStatus.INVITED)

        # The user domain roles exist
        self.assertTrue(
            UserDomainRole.objects.filter(
                user=self.user,
                domain=domain_in_portfolio_3,
            ).exists()
        )
        self.assertTrue(
            UserDomainRole.objects.filter(
                user=self.user,
                domain=domain_in_portfolio_4,
            ).exists()
        )
        self.assertTrue(
            UserDomainRole.objects.filter(
                user=self.user,
                domain=domain_not_in_portfolio_2,
            ).exists()
        )

        # Delete member (invite)
        self.invitation.delete()

        # Reload the objects from the database
        invite_1 = DomainInvitation.objects.get(pk=invite_1.pk)
        invite_2 = DomainInvitation.objects.get(pk=invite_2.pk)
        invite_3 = DomainInvitation.objects.get(pk=invite_3.pk)

        # The domain invitations to the portfolio domains have been canceled
        self.assertEqual(invite_1.status, DomainInvitation.DomainInvitationStatus.CANCELED)
        self.assertEqual(invite_2.status, DomainInvitation.DomainInvitationStatus.CANCELED)

        # Invite 3 is unaffected
        self.assertEqual(invite_3.status, DomainInvitation.DomainInvitationStatus.INVITED)

        # The user domain roles have been deleted for the domains in portfolio
        self.assertFalse(
            UserDomainRole.objects.filter(
                user=self.user,
                domain=domain_in_portfolio_3,
            ).exists()
        )
        self.assertFalse(
            UserDomainRole.objects.filter(
                user=self.user,
                domain=domain_in_portfolio_4,
            ).exists()
        )

        # The user domain role on the domain not in portfolio still exists
        self.assertTrue(
            UserDomainRole.objects.filter(
                user=self.user,
                domain=domain_not_in_portfolio_2,
            ).exists()
        )


class TestUserPortfolioPermission(TestCase):
    @less_console_noise_decorator
    def setUp(self):
        self.superuser = create_superuser()
        self.portfolio = Portfolio.objects.create(organization_name="Test Portfolio", requester=self.superuser)
        self.user, _ = User.objects.get_or_create(email="mayor@igorville.gov")
        self.user2, _ = User.objects.get_or_create(email="user2@igorville.gov", username="user2")
        super().setUp()

    def tearDown(self):
        super().tearDown()
        Domain.objects.all().delete()
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        DomainInvitation.objects.all().delete()
        UserPortfolioPermission.objects.all().delete()
        Portfolio.objects.all().delete()
        User.objects.all().delete()
        UserDomainRole.objects.all().delete()
        PortfolioInvitation.objects.all().delete()

    @less_console_noise_decorator
    @override_flag("multiple_portfolios", active=True)
    def test_clean_on_multiple_portfolios_when_flag_active(self):
        """Ensures that a user can create multiple portfolio permission objects when the flag is enabled"""
        # Create an instance of User with a portfolio but no roles or additional permissions
        portfolio, _ = Portfolio.objects.get_or_create(requester=self.user, organization_name="Hotel California")
        portfolio_2, _ = Portfolio.objects.get_or_create(requester=self.user, organization_name="Motel California")
        portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
            portfolio=portfolio, user=self.user, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )
        portfolio_permission_2 = UserPortfolioPermission(
            portfolio=portfolio_2, user=self.user, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )

        # Clean should pass on both of these objects
        try:
            portfolio_permission.clean()
            portfolio_permission_2.clean()
        except ValidationError as error:
            self.fail(f"Raised ValidationError unexpectedly: {error}")

    @less_console_noise_decorator
    @override_flag("multiple_portfolios", active=False)
    def test_clean_on_creates_multiple_portfolios(self):
        """Ensures that a user cannot create multiple portfolio permission objects when the flag is disabled"""
        # Create an instance of User with a single portfolio
        portfolio, _ = Portfolio.objects.get_or_create(requester=self.user, organization_name="Hotel California")
        portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
            portfolio=portfolio, user=self.user, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )
        portfolio_2, _ = Portfolio.objects.get_or_create(requester=self.user, organization_name="Motel California")
        portfolio_permission_2 = UserPortfolioPermission(
            portfolio=portfolio_2, user=self.user, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )
        # This should work as intended
        portfolio_permission.clean()

        # Test if the ValidationError is raised with the correct message
        with self.assertRaises(ValidationError) as cm:
            portfolio_permission_2.clean()

        self.assertEqual(
            cm.exception.message,
            (
                "This user is already assigned to a portfolio. "
                "Based on current waffle flag settings, users cannot be assigned to multiple portfolios."
            ),
        )

    @less_console_noise_decorator
    @override_flag("multiple_portfolios", active=False)
    def test_multiple_portfolio_reassignment(self):
        """Ensures that a user cannot be assigned to multiple portfolios based on reassignment"""
        # Create an instance of two users with separate portfolios
        portfolio, _ = Portfolio.objects.get_or_create(requester=self.user, organization_name="Hotel California")
        portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
            portfolio=portfolio, user=self.user, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )
        portfolio_2, _ = Portfolio.objects.get_or_create(requester=self.user2, organization_name="Motel California")
        portfolio_permission_2 = UserPortfolioPermission(
            portfolio=portfolio_2, user=self.user2, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )

        # This should work as intended
        portfolio_permission.clean()
        portfolio_permission_2.clean()

        # Reassign the portfolio of "user2" to "user" (this should throw an error
        # preventing "user" from having multiple portfolios)
        with self.assertRaises(ValidationError) as cm:
            portfolio_permission_2.user = self.user
            portfolio_permission_2.clean()

        self.assertEqual(
            cm.exception.message,
            (
                "This user is already assigned to a portfolio. "
                "Based on current waffle flag settings, users cannot be assigned to multiple portfolios."
            ),
        )

    @less_console_noise_decorator
    def test_get_managed_domains_count(self):
        """Test that the correct number of managed domains associated with the portfolio
        are returned."""
        # Add three domains, one which is in the portfolio and managed by the user,
        # one which is in the portfolio and not managed by the user,
        # and one which is managed by the user and not in the portfolio.
        # Arrange
        portfolio, _ = Portfolio.objects.get_or_create(requester=self.user, organization_name="Hotel California")
        test_user = create_test_user()
        portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
            portfolio=portfolio, user=test_user, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )
        # domain_in_portfolio should not be included in the count
        domain_in_portfolio, _ = Domain.objects.get_or_create(name="domain_in_portfolio.gov", state=Domain.State.READY)
        DomainInformation.objects.get_or_create(requester=self.user, domain=domain_in_portfolio, portfolio=portfolio)
        # domain_in_portfolio_and_managed should be included in the count
        domain_in_portfolio_and_managed, _ = Domain.objects.get_or_create(
            name="domain_in_portfolio_and_managed.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(
            requester=self.user, domain=domain_in_portfolio_and_managed, portfolio=portfolio
        )
        UserDomainRole.objects.get_or_create(
            user=test_user, domain=domain_in_portfolio_and_managed, role=UserDomainRole.Roles.MANAGER
        )
        # domain_managed should not be included in the count
        domain_managed, _ = Domain.objects.get_or_create(name="domain_managed.gov", state=Domain.State.READY)
        DomainInformation.objects.get_or_create(requester=self.user, domain=domain_managed)
        UserDomainRole.objects.get_or_create(user=test_user, domain=domain_managed, role=UserDomainRole.Roles.MANAGER)

        # Assert
        self.assertEqual(portfolio_permission.get_managed_domains_count(), 1)

    @less_console_noise_decorator
    def test_clean_user_portfolio_permission(self):
        """Tests validation of user portfolio permission"""

        # Test validation fails when portfolio missing but permissions are present
        permission = UserPortfolioPermission(user=self.superuser, roles=["organization_admin"], portfolio=None)
        with self.assertRaises(ValidationError) as err:
            permission.clean()
            self.assertEqual(
                str(err.exception),
                "When portfolio roles or additional permissions are assigned, portfolio is required.",
            )

        # Test validation fails when portfolio present but no permissions are present
        permission = UserPortfolioPermission(user=self.superuser, roles=None, portfolio=self.portfolio)
        with self.assertRaises(ValidationError) as err:
            permission.clean()
            self.assertEqual(
                str(err.exception),
                "When portfolio is assigned, portfolio roles or additional permissions are required.",
            )

        # Test validation fails with forbidden permissions for single role
        forbidden_member_roles = UserPortfolioPermission.FORBIDDEN_PORTFOLIO_ROLE_PERMISSIONS.get(
            UserPortfolioRoleChoices.ORGANIZATION_MEMBER
        )
        permission = UserPortfolioPermission(
            user=self.superuser,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            additional_permissions=forbidden_member_roles,
            portfolio=self.portfolio,
        )
        with self.assertRaises(ValidationError) as err:
            permission.clean()
            self.assertEqual(
                str(err.exception),
                "These permissions cannot be assigned to Member: "
                "<Create and edit members, View all domains and domain reports, View members>",
            )

    @less_console_noise_decorator
    @override_flag("multiple_portfolios", active=False)
    def test_clean_user_portfolio_permission_multiple_portfolios_flag_off_and_duplicate_permission(self):
        """Test validation of multiple_portfolios flag.
        Scenario 1: Flag is inactive, and the user has existing portfolio permissions"""

        # existing permission
        UserPortfolioPermission.objects.create(
            user=self.superuser,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            portfolio=self.portfolio,
        )

        permission = UserPortfolioPermission(
            user=self.superuser,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            portfolio=self.portfolio,
        )

        with self.assertRaises(ValidationError) as err:
            permission.clean()

        self.assertEqual(
            str(err.exception.messages[0]),
            "This user is already assigned to a portfolio. "
            "Based on current waffle flag settings, users cannot be assigned to multiple portfolios.",
        )

    @less_console_noise_decorator
    @override_flag("multiple_portfolios", active=False)
    def test_clean_user_portfolio_permission_multiple_portfolios_flag_off_and_existing_invitation(self):
        """Test validation of multiple_portfolios flag.
        Scenario 2: Flag is inactive, and the user has existing portfolio invitation to another portfolio"""

        portfolio2 = Portfolio.objects.create(requester=self.superuser, organization_name="Joey go away")

        PortfolioInvitation.objects.create(
            email=self.superuser.email, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN], portfolio=portfolio2
        )

        permission = UserPortfolioPermission(
            user=self.superuser,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            portfolio=self.portfolio,
        )

        with self.assertRaises(ValidationError) as err:
            permission.clean()

        self.assertEqual(
            str(err.exception.messages[0]),
            "This user is already assigned to a portfolio invitation. "
            "Based on current waffle flag settings, users cannot be assigned to multiple portfolios.",
        )

    @less_console_noise_decorator
    @override_flag("multiple_portfolios", active=True)
    def test_clean_user_portfolio_permission_multiple_portfolios_flag_on_and_duplicate_permission(self):
        """Test validation of multiple_portfolios flag.
        Scenario 3: Flag is active, and the user has existing portfolio invitation"""

        # existing permission
        UserPortfolioPermission.objects.create(
            user=self.superuser,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            portfolio=self.portfolio,
        )

        permission = UserPortfolioPermission(
            user=self.superuser,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            portfolio=self.portfolio,
        )

        # Should not raise any exceptions
        try:
            permission.clean()
        except ValidationError:
            self.fail("ValidationError was raised unexpectedly when flag is active.")

    @less_console_noise_decorator
    @override_flag("multiple_portfolios", active=True)
    def test_clean_user_portfolio_permission_multiple_portfolios_flag_on_and_existing_invitation(self):
        """Test validation of multiple_portfolios flag.
        Scenario 4: Flag is active, and the user has existing portfolio invitation to another portfolio"""

        portfolio2 = Portfolio.objects.create(requester=self.superuser, organization_name="Joey go away")

        PortfolioInvitation.objects.create(
            email=self.superuser.email, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN], portfolio=portfolio2
        )

        permission = UserPortfolioPermission(
            user=self.superuser,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            portfolio=self.portfolio,
        )

        # Should not raise any exceptions
        try:
            permission.clean()
        except ValidationError:
            self.fail("ValidationError was raised unexpectedly when flag is active.")

    @less_console_noise_decorator
    def test_get_forbidden_permissions_with_multiple_roles(self):
        """Tests that forbidden permissions are properly handled when a user has multiple roles"""
        # Get forbidden permissions for member role
        member_forbidden = UserPortfolioPermission.FORBIDDEN_PORTFOLIO_ROLE_PERMISSIONS.get(
            UserPortfolioRoleChoices.ORGANIZATION_MEMBER
        )

        # Test with both admin and member roles
        roles = [UserPortfolioRoleChoices.ORGANIZATION_ADMIN, UserPortfolioRoleChoices.ORGANIZATION_MEMBER]

        # These permissions would be forbidden for member alone, but should be allowed
        # when combined with admin role
        permissions = UserPortfolioPermission.get_forbidden_permissions(
            roles=roles, additional_permissions=member_forbidden
        )

        # Should return empty set since no permissions are commonly forbidden between admin and member
        self.assertEqual(permissions, set())

        # Verify the same permissions are forbidden when only member role is present
        member_only_permissions = UserPortfolioPermission.get_forbidden_permissions(
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER], additional_permissions=member_forbidden
        )

        # Should return the forbidden permissions for member role
        self.assertEqual(member_only_permissions, set(member_forbidden))

    @less_console_noise_decorator
    def test_delete_portfolio_permission_deletes_user_domain_roles(self):
        """Deleting a user portfolio permission causes domain invitations for the same email on the same
        portfolio to be canceled, also deletes any exiting user domain roles on the portfolio for the
        user if the user exists."""

        domain_in_portfolio_1, _ = Domain.objects.get_or_create(
            name="domain_in_portfolio_1.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(
            requester=self.user, domain=domain_in_portfolio_1, portfolio=self.portfolio
        )
        invite_1, _ = DomainInvitation.objects.get_or_create(email=self.user.email, domain=domain_in_portfolio_1)

        domain_in_portfolio_2, _ = Domain.objects.get_or_create(
            name="domain_in_portfolio_and_invited_2.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(
            requester=self.user, domain=domain_in_portfolio_2, portfolio=self.portfolio
        )
        invite_2, _ = DomainInvitation.objects.get_or_create(email=self.user.email, domain=domain_in_portfolio_2)

        domain_in_portfolio_3, _ = Domain.objects.get_or_create(
            name="domain_in_portfolio_3.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(
            requester=self.user, domain=domain_in_portfolio_3, portfolio=self.portfolio
        )
        UserDomainRole.objects.get_or_create(
            user=self.user, domain=domain_in_portfolio_3, role=UserDomainRole.Roles.MANAGER
        )

        domain_in_portfolio_4, _ = Domain.objects.get_or_create(
            name="domain_in_portfolio_and_invited_4.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(
            requester=self.user, domain=domain_in_portfolio_4, portfolio=self.portfolio
        )
        UserDomainRole.objects.get_or_create(
            user=self.user, domain=domain_in_portfolio_4, role=UserDomainRole.Roles.MANAGER
        )

        domain_not_in_portfolio_1, _ = Domain.objects.get_or_create(
            name="domain_not_in_portfolio.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(requester=self.user, domain=domain_not_in_portfolio_1)
        invite_3, _ = DomainInvitation.objects.get_or_create(email=self.user.email, domain=domain_not_in_portfolio_1)

        domain_not_in_portfolio_2, _ = Domain.objects.get_or_create(
            name="domain_not_in_portfolio_2.gov", state=Domain.State.READY
        )
        DomainInformation.objects.get_or_create(requester=self.user, domain=domain_not_in_portfolio_2)
        UserDomainRole.objects.get_or_create(
            user=self.user, domain=domain_not_in_portfolio_2, role=UserDomainRole.Roles.MANAGER
        )

        # Create portfolio permission
        portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
            portfolio=self.portfolio, user=self.user, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )

        # The domain invitations start off as INVITED
        self.assertEqual(invite_1.status, DomainInvitation.DomainInvitationStatus.INVITED)
        self.assertEqual(invite_2.status, DomainInvitation.DomainInvitationStatus.INVITED)
        self.assertEqual(invite_3.status, DomainInvitation.DomainInvitationStatus.INVITED)

        # The user domain roles exist
        self.assertTrue(
            UserDomainRole.objects.filter(
                user=self.user,
                domain=domain_in_portfolio_3,
            ).exists()
        )
        self.assertTrue(
            UserDomainRole.objects.filter(
                user=self.user,
                domain=domain_in_portfolio_4,
            ).exists()
        )
        self.assertTrue(
            UserDomainRole.objects.filter(
                user=self.user,
                domain=domain_not_in_portfolio_2,
            ).exists()
        )

        # Delete member (user portfolio permission)
        portfolio_permission.delete()

        # Reload the objects from the database
        invite_1 = DomainInvitation.objects.get(pk=invite_1.pk)
        invite_2 = DomainInvitation.objects.get(pk=invite_2.pk)
        invite_3 = DomainInvitation.objects.get(pk=invite_3.pk)

        # The domain invitations to the portfolio domains have been canceled
        self.assertEqual(invite_1.status, DomainInvitation.DomainInvitationStatus.CANCELED)
        self.assertEqual(invite_2.status, DomainInvitation.DomainInvitationStatus.CANCELED)

        # Invite 3 is unaffected
        self.assertEqual(invite_3.status, DomainInvitation.DomainInvitationStatus.INVITED)

        # The user domain roles have been deleted for the domains in portfolio
        self.assertFalse(
            UserDomainRole.objects.filter(
                user=self.user,
                domain=domain_in_portfolio_3,
            ).exists()
        )
        self.assertFalse(
            UserDomainRole.objects.filter(
                user=self.user,
                domain=domain_in_portfolio_4,
            ).exists()
        )

        # The user domain role on the domain not in portfolio still exists
        self.assertTrue(
            UserDomainRole.objects.filter(
                user=self.user,
                domain=domain_not_in_portfolio_2,
            ).exists()
        )


class TestUser(TestCase):
    """Test actions that occur on user login,
    test class method that controls how users get validated."""

    @less_console_noise_decorator
    def setUp(self):
        self.email = "mayor@igorville.gov"
        self.domain_name = "igorvilleInTransition.gov"
        self.domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        self.user, _ = User.objects.get_or_create(email=self.email)
        self.factory = RequestFactory()
        self.portfolio = Portfolio.objects.create(organization_name="Test Portfolio", requester=self.user)

    def tearDown(self):
        super().tearDown()
        Domain.objects.all().delete()
        DomainInvitation.objects.all().delete()
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        DraftDomain.objects.all().delete()
        TransitionDomain.objects.all().delete()
        UserPortfolioPermission.objects.all().delete()
        Portfolio.objects.all().delete()
        User.objects.all().delete()
        UserDomainRole.objects.all().delete()

    @patch("registrar.models.User._has_portfolio_permission")
    def test_has_view_portfolio_permission(self, mock_has_permission):
        mock_has_permission.return_value = True

        self.assertTrue(self.user.has_view_portfolio_permission(self.portfolio))
        mock_has_permission.assert_called_once_with(self.portfolio, UserPortfolioPermissionChoices.VIEW_PORTFOLIO)

    @patch("registrar.models.User._has_portfolio_permission")
    def test_has_edit_portfolio_permission(self, mock_has_permission):
        mock_has_permission.return_value = True

        self.assertTrue(self.user.has_edit_portfolio_permission(self.portfolio))
        mock_has_permission.assert_called_once_with(self.portfolio, UserPortfolioPermissionChoices.EDIT_PORTFOLIO)

    @patch("registrar.models.User._has_portfolio_permission")
    def test_has_any_domains_portfolio_permission(self, mock_has_permission):
        mock_has_permission.side_effect = [False, True]  # First permission false, second permission true

        self.assertTrue(self.user.has_any_domains_portfolio_permission(self.portfolio))
        self.assertEqual(mock_has_permission.call_count, 2)
        mock_has_permission.assert_any_call(self.portfolio, UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS)
        mock_has_permission.assert_any_call(self.portfolio, UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS)

    @patch("registrar.models.User._has_portfolio_permission")
    def test_has_view_all_domains_portfolio_permission(self, mock_has_permission):
        mock_has_permission.return_value = True

        self.assertTrue(self.user.has_view_all_domains_portfolio_permission(self.portfolio))
        mock_has_permission.assert_called_once_with(self.portfolio, UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS)

    @patch("registrar.models.User._has_portfolio_permission")
    def test_has_any_requests_portfolio_permission(self, mock_has_permission):
        mock_has_permission.side_effect = [False, True]  # First permission false, second permission true

        self.assertTrue(self.user.has_any_requests_portfolio_permission(self.portfolio))
        self.assertEqual(mock_has_permission.call_count, 2)
        mock_has_permission.assert_any_call(self.portfolio, UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS)
        mock_has_permission.assert_any_call(self.portfolio, UserPortfolioPermissionChoices.EDIT_REQUESTS)

    @patch("registrar.models.User._has_portfolio_permission")
    def test_has_view_all_requests_portfolio_permission(self, mock_has_permission):
        mock_has_permission.return_value = True

        self.assertTrue(self.user.has_view_all_requests_portfolio_permission(self.portfolio))
        mock_has_permission.assert_called_once_with(self.portfolio, UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS)

    @patch("registrar.models.User._has_portfolio_permission")
    def test_has_edit_request_portfolio_permission(self, mock_has_permission):
        mock_has_permission.return_value = True

        self.assertTrue(self.user.has_edit_request_portfolio_permission(self.portfolio))
        mock_has_permission.assert_called_once_with(self.portfolio, UserPortfolioPermissionChoices.EDIT_REQUESTS)

    @less_console_noise_decorator
    def test_check_transition_domains_without_domains_on_login(self):
        """A user's on_each_login callback does not check transition domains.
        This test makes sure that in the event a domain does not exist
        for a given transition domain, both a domain and domain invitation
        are created."""
        self.user.on_each_login()
        self.assertFalse(Domain.objects.filter(name=self.domain_name).exists())

    @less_console_noise_decorator
    def test_identity_verification_with_domain_manager(self):
        """A domain manager should return False when tested with class
        method needs_identity_verification"""
        UserDomainRole.objects.get_or_create(user=self.user, domain=self.domain, role=UserDomainRole.Roles.MANAGER)
        self.assertFalse(User.needs_identity_verification(self.user.email, self.user.username))

    @less_console_noise_decorator
    def test_identity_verification_with_transition_user(self):
        """A user from the Verisign transition should return False
        when tested with class method needs_identity_verification"""
        TransitionDomain.objects.get_or_create(username=self.user.email, domain_name=self.domain_name)
        self.assertFalse(User.needs_identity_verification(self.user.email, self.user.username))

    @less_console_noise_decorator
    def test_identity_verification_with_very_important_person(self):
        """A Very Important Person should return False
        when tested with class method needs_identity_verification"""
        VerifiedByStaff.objects.get_or_create(email=self.user.email)
        self.assertFalse(User.needs_identity_verification(self.user.email, self.user.username))

    @less_console_noise_decorator
    def test_identity_verification_with_invited_user(self):
        """An invited user should return False when tested with class
        method needs_identity_verification"""
        DomainInvitation.objects.get_or_create(email=self.user.email, domain=self.domain)
        self.assertFalse(User.needs_identity_verification(self.user.email, self.user.username))

    @less_console_noise_decorator
    def test_identity_verification_with_new_user(self):
        """A new user who's neither transitioned nor invited should
        return True when tested with class method needs_identity_verification"""
        self.assertTrue(User.needs_identity_verification(self.user.email, self.user.username))

    @less_console_noise_decorator
    def test_check_domain_invitations_on_login_caps_email(self):
        """A DomainInvitation with an email address with capital letters should match
        a User record whose email address is not in caps"""
        # create DomainInvitation with CAPS email that matches User email
        # on a case-insensitive match
        caps_email = "MAYOR@igorville.gov"
        # mock the domain invitation save routine
        with patch("registrar.models.DomainInvitation.save") as save_mock:
            DomainInvitation.objects.get_or_create(email=caps_email, domain=self.domain)
            self.user.check_domain_invitations_on_login()
            # if check_domain_invitations_on_login properly matches exactly one
            # Domain Invitation, then save routine should be called exactly once
            save_mock.assert_called_once()

    @less_console_noise_decorator
    def test_approved_domains_count(self):
        """Test that the correct approved domain count is returned for a user"""
        # with no associated approved domains, expect this to return 0
        self.assertEquals(self.user.get_approved_domains_count(), 0)
        # with one approved domain, expect this to return 1
        UserDomainRole.objects.get_or_create(user=self.user, domain=self.domain, role=UserDomainRole.Roles.MANAGER)
        self.assertEquals(self.user.get_approved_domains_count(), 1)
        # with one approved domain, expect this to return 1 (domain2 is deleted, so not considered approved)
        domain2, _ = Domain.objects.get_or_create(name="igorville2.gov", state=Domain.State.DELETED)
        UserDomainRole.objects.get_or_create(user=self.user, domain=domain2, role=UserDomainRole.Roles.MANAGER)
        self.assertEquals(self.user.get_approved_domains_count(), 1)
        # with two approved domains, expect this to return 2
        domain3, _ = Domain.objects.get_or_create(name="igorville3.gov", state=Domain.State.DNS_NEEDED)
        UserDomainRole.objects.get_or_create(user=self.user, domain=domain3, role=UserDomainRole.Roles.MANAGER)
        self.assertEquals(self.user.get_approved_domains_count(), 2)
        # with three approved domains, expect this to return 3
        domain4, _ = Domain.objects.get_or_create(name="igorville4.gov", state=Domain.State.ON_HOLD)
        UserDomainRole.objects.get_or_create(user=self.user, domain=domain4, role=UserDomainRole.Roles.MANAGER)
        self.assertEquals(self.user.get_approved_domains_count(), 3)
        # with four approved domains, expect this to return 4
        domain5, _ = Domain.objects.get_or_create(name="igorville5.gov", state=Domain.State.READY)
        UserDomainRole.objects.get_or_create(user=self.user, domain=domain5, role=UserDomainRole.Roles.MANAGER)
        self.assertEquals(self.user.get_approved_domains_count(), 4)

    @less_console_noise_decorator
    def test_active_requests_count(self):
        """Test that the correct active domain requests count is returned for a user"""
        # with no associated active requests, expect this to return 0
        self.assertEquals(self.user.get_active_requests_count(), 0)
        # with one active request, expect this to return 1
        draft_domain, _ = DraftDomain.objects.get_or_create(name="igorville1.gov")
        DomainRequest.objects.create(
            requester=self.user, requested_domain=draft_domain, status=DomainRequest.DomainRequestStatus.SUBMITTED
        )
        self.assertEquals(self.user.get_active_requests_count(), 1)
        # with two active requests, expect this to return 2
        draft_domain, _ = DraftDomain.objects.get_or_create(name="igorville2.gov")
        DomainRequest.objects.create(
            requester=self.user, requested_domain=draft_domain, status=DomainRequest.DomainRequestStatus.IN_REVIEW
        )
        self.assertEquals(self.user.get_active_requests_count(), 2)
        # with three active requests, expect this to return 3
        draft_domain, _ = DraftDomain.objects.get_or_create(name="igorville3.gov")
        DomainRequest.objects.create(
            requester=self.user, requested_domain=draft_domain, status=DomainRequest.DomainRequestStatus.ACTION_NEEDED
        )
        self.assertEquals(self.user.get_active_requests_count(), 3)
        # with three active requests, expect this to return 3 (STARTED is not considered active)
        draft_domain, _ = DraftDomain.objects.get_or_create(name="igorville4.gov")
        DomainRequest.objects.create(
            requester=self.user, requested_domain=draft_domain, status=DomainRequest.DomainRequestStatus.STARTED
        )
        self.assertEquals(self.user.get_active_requests_count(), 3)

    @less_console_noise_decorator
    def test_rejected_requests_count(self):
        """Test that the correct rejected domain requests count is returned for a user"""
        # with no associated rejected requests, expect this to return 0
        self.assertEquals(self.user.get_rejected_requests_count(), 0)
        # with one rejected request, expect this to return 1
        draft_domain, _ = DraftDomain.objects.get_or_create(name="igorville1.gov")
        DomainRequest.objects.create(
            requester=self.user, requested_domain=draft_domain, status=DomainRequest.DomainRequestStatus.REJECTED
        )
        self.assertEquals(self.user.get_rejected_requests_count(), 1)

    @less_console_noise_decorator
    def test_ineligible_requests_count(self):
        """Test that the correct ineligible domain requests count is returned for a user"""
        # with no associated ineligible requests, expect this to return 0
        self.assertEquals(self.user.get_ineligible_requests_count(), 0)
        # with one ineligible request, expect this to return 1
        draft_domain, _ = DraftDomain.objects.get_or_create(name="igorville1.gov")
        DomainRequest.objects.create(
            requester=self.user, requested_domain=draft_domain, status=DomainRequest.DomainRequestStatus.INELIGIBLE
        )
        self.assertEquals(self.user.get_ineligible_requests_count(), 1)

    @less_console_noise_decorator
    def test_has_contact_info(self):
        """Test that has_contact_info properly returns"""
        # test with a user with contact info defined
        self.assertTrue(self.user.has_contact_info())
        # test with a user without contact info defined
        self.user.title = None
        self.user.email = None
        self.user.phone = None
        self.assertFalse(self.user.has_contact_info())

    @less_console_noise_decorator
    def test_has_portfolio_permission(self):
        """
        0. Returns False when user does not have a permission
        1. Returns False when a user does not have a portfolio
        2. Returns True when user has direct permission
        3. Returns True when user has permission through a role

        Note: This tests _get_portfolio_permissions as a side effect
        """

        portfolio, _ = Portfolio.objects.get_or_create(requester=self.user, organization_name="Hotel California")

        user_can_view_all_domains = self.user.has_any_domains_portfolio_permission(portfolio)
        user_can_view_all_requests = self.user.has_any_requests_portfolio_permission(portfolio)

        self.assertFalse(user_can_view_all_domains)
        self.assertFalse(user_can_view_all_requests)

        portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
            portfolio=portfolio,
            user=self.user,
            additional_permissions=[
                UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
                UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS,
            ],
        )

        user_can_view_all_domains = self.user.has_any_domains_portfolio_permission(portfolio)
        user_can_view_all_requests = self.user.has_any_requests_portfolio_permission(portfolio)

        self.assertTrue(user_can_view_all_domains)
        self.assertFalse(user_can_view_all_requests)

        portfolio_permission.roles = [UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        portfolio_permission.save()
        portfolio_permission.refresh_from_db()

        user_can_view_all_domains = self.user.has_any_domains_portfolio_permission(portfolio)
        user_can_view_all_requests = self.user.has_any_requests_portfolio_permission(portfolio)

        self.assertTrue(user_can_view_all_domains)
        self.assertTrue(user_can_view_all_requests)

        UserDomainRole.objects.get_or_create(user=self.user, domain=self.domain, role=UserDomainRole.Roles.MANAGER)

        user_can_view_all_domains = self.user.has_any_domains_portfolio_permission(portfolio)
        user_can_view_all_requests = self.user.has_any_requests_portfolio_permission(portfolio)

        self.assertTrue(user_can_view_all_domains)
        self.assertTrue(user_can_view_all_requests)

        Portfolio.objects.all().delete()

    @less_console_noise_decorator
    def test_user_with_portfolio_but_no_roles(self):
        # Create an instance of User with a portfolio but no roles or additional permissions
        portfolio, _ = Portfolio.objects.get_or_create(requester=self.user, organization_name="Hotel California")
        portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(portfolio=portfolio, user=self.user)

        # Try to remove the role
        portfolio_permission.portfolio = portfolio
        portfolio_permission.roles = []

        # Test if the ValidationError is raised with the correct message
        with self.assertRaises(ValidationError) as cm:
            portfolio_permission.clean()

        self.assertEqual(
            cm.exception.message, "When portfolio is assigned, portfolio roles or additional permissions are required."
        )
        Portfolio.objects.all().delete()

    @less_console_noise_decorator
    def test_user_with_portfolio_roles_but_no_portfolio(self):
        portfolio, _ = Portfolio.objects.get_or_create(requester=self.user, organization_name="Hotel California")
        portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
            portfolio=portfolio, user=self.user, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )

        # Try to remove the portfolio
        portfolio_permission.portfolio = None
        portfolio_permission.roles = [UserPortfolioRoleChoices.ORGANIZATION_ADMIN]

        # Test if the ValidationError is raised with the correct message
        with self.assertRaises(ValidationError) as cm:
            portfolio_permission.clean()

        self.assertEqual(
            cm.exception.message, "When portfolio roles or additional permissions are assigned, portfolio is required."
        )

    @less_console_noise_decorator
    def test_user_with_admin_portfolio_role(self):
        portfolio, _ = Portfolio.objects.get_or_create(requester=self.user, organization_name="Hotel California")
        self.assertFalse(self.user.is_portfolio_admin(portfolio))
        UserPortfolioPermission.objects.get_or_create(
            portfolio=portfolio, user=self.user, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )
        self.assertTrue(self.user.is_portfolio_admin(portfolio))

    @less_console_noise_decorator
    def test_get_active_requests_count_in_portfolio_returns_zero_if_no_portfolio(self):
        # There is no portfolio referenced in session so should return 0
        request = self.factory.get("/")
        request.session = {}

        count = self.user.get_active_requests_count_in_portfolio(request)
        self.assertEqual(count, 0)

    @less_console_noise_decorator
    def test_get_active_requests_count_in_portfolio_returns_count_if_portfolio(self):
        request = self.factory.get("/")
        request.session = {"portfolio": self.portfolio}

        # Create active requests
        domain_1, _ = DraftDomain.objects.get_or_create(name="meoward1.gov")
        domain_2, _ = DraftDomain.objects.get_or_create(name="meoward2.gov")
        domain_3, _ = DraftDomain.objects.get_or_create(name="meoward3.gov")
        domain_4, _ = DraftDomain.objects.get_or_create(name="meoward4.gov")

        # Create 3 active requests + 1 that isn't
        DomainRequest.objects.create(
            requester=self.user,
            requested_domain=domain_1,
            status=DomainRequest.DomainRequestStatus.SUBMITTED,
            portfolio=self.portfolio,
        )
        DomainRequest.objects.create(
            requester=self.user,
            requested_domain=domain_2,
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
            portfolio=self.portfolio,
        )
        DomainRequest.objects.create(
            requester=self.user,
            requested_domain=domain_3,
            status=DomainRequest.DomainRequestStatus.ACTION_NEEDED,
            portfolio=self.portfolio,
        )
        DomainRequest.objects.create(  # This one should not be counted
            requester=self.user,
            requested_domain=domain_4,
            status=DomainRequest.DomainRequestStatus.REJECTED,
            portfolio=self.portfolio,
        )

        count = self.user.get_active_requests_count_in_portfolio(request)
        self.assertEqual(count, 3)

    @less_console_noise_decorator
    def test_is_only_admin_of_portfolio_returns_true(self):
        # Create user as the only admin of the portfolio
        UserPortfolioPermission.objects.create(
            user=self.user, portfolio=self.portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )
        self.assertTrue(self.user.is_only_admin_of_portfolio(self.portfolio))

    @less_console_noise_decorator
    def test_is_only_admin_of_portfolio_returns_false_if_no_admins(self):
        # No admin for the portfolio
        self.assertFalse(self.user.is_only_admin_of_portfolio(self.portfolio))

    @less_console_noise_decorator
    def test_is_only_admin_of_portfolio_returns_false_if_multiple_admins(self):
        # Create multiple admins for the same portfolio
        UserPortfolioPermission.objects.create(
            user=self.user, portfolio=self.portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )
        # Create another user within this test
        other_user = User.objects.create(email="second_admin@igorville.gov", username="second_admin")
        UserPortfolioPermission.objects.create(
            user=other_user, portfolio=self.portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )
        self.assertFalse(self.user.is_only_admin_of_portfolio(self.portfolio))

    @less_console_noise_decorator
    def test_is_only_admin_of_portfolio_returns_false_if_user_not_admin(self):
        # Create other_user for same portfolio and is given admin access
        other_user = User.objects.create(email="second_admin@igorville.gov", username="second_admin")

        UserPortfolioPermission.objects.create(
            user=other_user, portfolio=self.portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )
        # User doesn't have admin access so should return false
        self.assertFalse(self.user.is_only_admin_of_portfolio(self.portfolio))

    @less_console_noise_decorator
    def test_email_is_with_normalize(self):
        mixed_case_email = "SOME_user@igorville.gov"
        user = User.objects.create(email=mixed_case_email, username="some_user")
        self.assertEqual(user.email, "some_user@igorville.gov")

    @less_console_noise_decorator
    def test_empty_email_with_normalize(self):
        user = User.objects.create(username="user_without_email")
        self.assertEqual(user.email, "")


class TestContact(TestCase):
    @less_console_noise_decorator
    def setUp(self):
        self.email = "mayor@igorville.gov"
        self.user, _ = User.objects.get_or_create(
            email=self.email, first_name="Jeff", last_name="Lebowski", phone="123456789"
        )
        self.contact, _ = Contact.objects.get_or_create(
            first_name="Jeff",
            last_name="Lebowski",
        )

        self.contact_as_so, _ = Contact.objects.get_or_create(email="newguy@igorville.gov")
        self.domain_request = DomainRequest.objects.create(requester=self.user, senior_official=self.contact_as_so)

    def tearDown(self):
        super().tearDown()
        DomainRequest.objects.all().delete()
        Contact.objects.all().delete()
        User.objects.all().delete()

    def test_has_more_than_one_join(self):
        """Test the Contact model method, has_more_than_one_join"""
        # test for a contact which is assigned as a senior official on a domain request
        self.assertFalse(self.contact_as_so.has_more_than_one_join("senior_official"))
        self.assertTrue(self.contact_as_so.has_more_than_one_join("submitted_domain_requests"))

    @less_console_noise_decorator
    def test_has_contact_info(self):
        """Test that has_contact_info properly returns"""
        self.contact.title = "Title"
        # test with a contact with contact info defined
        self.assertTrue(self.contact.has_contact_info())
        # test with a contact without contact info defined
        self.contact.title = None
        self.contact.email = None
        self.contact.phone = None
        self.assertFalse(self.contact.has_contact_info())


class TestDomainRequestCustomSave(TestCase):
    """Tests custom save behaviour on the DomainRequest object"""

    def tearDown(self):
        DomainRequest.objects.all().delete()
        super().tearDown()

    @less_console_noise_decorator
    def test_create_or_update_organization_type_new_instance(self):
        """Test create_or_update_organization_type when creating a new instance"""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=True,
        )

        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION)

    @less_console_noise_decorator
    def test_create_or_update_organization_type_new_instance_federal_does_nothing(self):
        """Test if create_or_update_organization_type does nothing when creating a new instance for federal"""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.FEDERAL,
            is_election_board=True,
        )
        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.FEDERAL)
        self.assertEqual(domain_request.is_election_board, None)

    @less_console_noise_decorator
    def test_create_or_update_organization_type_existing_instance_updates_election_board(self):
        """Test create_or_update_organization_type for an existing instance."""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=False,
        )
        domain_request.is_election_board = True
        domain_request.save()

        self.assertEqual(domain_request.is_election_board, True)
        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION)

        # Try reverting the election board value
        domain_request.is_election_board = False
        domain_request.save()

        self.assertEqual(domain_request.is_election_board, False)
        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY)

    @less_console_noise_decorator
    def test_existing_instance_updates_election_board_to_none(self):
        """Test create_or_update_organization_type for an existing instance, first to True and then to None.
        Start our with is_election_board as none to simulate a situation where the request was started, but
        only completed to the point of filling out the generic_org_type."""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=None,
        )
        domain_request.is_election_board = True
        domain_request.save()

        self.assertEqual(domain_request.is_election_board, True)
        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION)

        # Try reverting the election board value.
        domain_request.is_election_board = None
        domain_request.save()

        self.assertEqual(domain_request.is_election_board, None)
        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY)

    @less_console_noise_decorator
    def test_create_or_update_organization_type_existing_instance_updates_generic_org_type(self):
        """Test create_or_update_organization_type when modifying generic_org_type on an existing instance."""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=True,
        )

        domain_request.generic_org_type = DomainRequest.OrganizationChoices.INTERSTATE
        domain_request.save()

        # Election board should be None because interstate cannot have an election board.
        self.assertEqual(domain_request.is_election_board, None)
        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.INTERSTATE)

        # Try changing the org Type to something that CAN have an election board.
        domain_request_tribal = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="startedTribal.gov",
            generic_org_type=DomainRequest.OrganizationChoices.TRIBAL,
            is_election_board=True,
        )
        self.assertEqual(
            domain_request_tribal.organization_type, DomainRequest.OrgChoicesElectionOffice.TRIBAL_ELECTION
        )

        # Change the org type
        domain_request_tribal.generic_org_type = DomainRequest.OrganizationChoices.STATE_OR_TERRITORY
        domain_request_tribal.save()

        self.assertEqual(domain_request_tribal.is_election_board, True)
        self.assertEqual(
            domain_request_tribal.organization_type, DomainRequest.OrgChoicesElectionOffice.STATE_OR_TERRITORY_ELECTION
        )

    @less_console_noise_decorator
    def test_create_or_update_organization_type_no_update(self):
        """Test create_or_update_organization_type when there are no values to update."""

        # Test for when both generic_org_type and organization_type is declared,
        # and are both non-election board
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=False,
        )
        domain_request.save()
        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY)
        self.assertEqual(domain_request.is_election_board, False)
        self.assertEqual(domain_request.generic_org_type, DomainRequest.OrganizationChoices.CITY)

        # Test for when both generic_org_type and organization_type is declared,
        # and are both election board
        domain_request_election = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="startedElection.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=True,
            organization_type=DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION,
        )

        self.assertEqual(
            domain_request_election.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION
        )
        self.assertEqual(domain_request_election.is_election_board, True)
        self.assertEqual(domain_request_election.generic_org_type, DomainRequest.OrganizationChoices.CITY)

        # Modify an unrelated existing value for both, and ensure that everything is still consistent
        domain_request.city = "Fudge"
        domain_request_election.city = "Caramel"
        domain_request.save()
        domain_request_election.save()

        self.assertEqual(domain_request.city, "Fudge")
        self.assertEqual(domain_request_election.city, "Caramel")

        # Test for non-election
        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY)
        self.assertEqual(domain_request.is_election_board, False)
        self.assertEqual(domain_request.generic_org_type, DomainRequest.OrganizationChoices.CITY)

        # Test for election
        self.assertEqual(
            domain_request_election.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION
        )
        self.assertEqual(domain_request_election.is_election_board, True)
        self.assertEqual(domain_request_election.generic_org_type, DomainRequest.OrganizationChoices.CITY)


class TestDomainInformationCustomSave(TestCase):
    """Tests custom save behaviour on the DomainInformation object"""

    def tearDown(self):
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        Domain.objects.all().delete()
        super().tearDown()

    @less_console_noise_decorator
    def test_create_or_update_organization_type_new_instance(self):
        """Test create_or_update_organization_type when creating a new instance"""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=True,
        )

        domain_information = DomainInformation.create_from_dr(domain_request)
        self.assertEqual(domain_information.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION)

    @less_console_noise_decorator
    def test_create_or_update_organization_type_new_instance_federal_does_nothing(self):
        """Test if create_or_update_organization_type does nothing when creating a new instance for federal"""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.FEDERAL,
            is_election_board=True,
        )

        domain_information = DomainInformation.create_from_dr(domain_request)
        self.assertEqual(domain_information.organization_type, DomainRequest.OrgChoicesElectionOffice.FEDERAL)
        self.assertEqual(domain_information.is_election_board, None)

    @less_console_noise_decorator
    def test_create_or_update_organization_type_existing_instance_updates_election_board(self):
        """Test create_or_update_organization_type for an existing instance."""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=False,
        )
        domain_information = DomainInformation.create_from_dr(domain_request)
        domain_information.is_election_board = True
        domain_information.save()

        self.assertEqual(domain_information.is_election_board, True)
        self.assertEqual(domain_information.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION)

        # Try reverting the election board value
        domain_information.is_election_board = False
        domain_information.save()
        domain_information.refresh_from_db()

        self.assertEqual(domain_information.is_election_board, False)
        self.assertEqual(domain_information.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY)

    @less_console_noise_decorator
    def test_existing_instance_update_election_board_to_none(self):
        """Test create_or_update_organization_type for an existing instance, first to True and then to None.
        Start our with is_election_board as none to simulate a situation where the request was started, but
        only completed to the point of filling out the generic_org_type."""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=None,
        )
        domain_information = DomainInformation.create_from_dr(domain_request)
        domain_information.is_election_board = True
        domain_information.save()

        self.assertEqual(domain_information.is_election_board, True)
        self.assertEqual(domain_information.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION)

        # Try reverting the election board value
        domain_information.is_election_board = None
        domain_information.save()
        domain_information.refresh_from_db()

        self.assertEqual(domain_information.is_election_board, None)
        self.assertEqual(domain_information.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY)

    @less_console_noise_decorator
    def test_create_or_update_organization_type_existing_instance_updates_generic_org_type(self):
        """Test create_or_update_organization_type when modifying generic_org_type on an existing instance."""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=True,
        )
        domain_information = DomainInformation.create_from_dr(domain_request)

        domain_information.generic_org_type = DomainRequest.OrganizationChoices.INTERSTATE
        domain_information.save()

        # Election board should be None because interstate cannot have an election board.
        self.assertEqual(domain_information.is_election_board, None)
        self.assertEqual(domain_information.organization_type, DomainRequest.OrgChoicesElectionOffice.INTERSTATE)

        # Try changing the org Type to something that CAN have an election board.
        domain_request_tribal = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="startedTribal.gov",
            generic_org_type=DomainRequest.OrganizationChoices.TRIBAL,
            is_election_board=True,
        )
        domain_information_tribal = DomainInformation.create_from_dr(domain_request_tribal)
        self.assertEqual(
            domain_information_tribal.organization_type, DomainRequest.OrgChoicesElectionOffice.TRIBAL_ELECTION
        )

        # Change the org type
        domain_information_tribal.generic_org_type = DomainRequest.OrganizationChoices.STATE_OR_TERRITORY
        domain_information_tribal.save()

        self.assertEqual(domain_information_tribal.is_election_board, True)
        self.assertEqual(
            domain_information_tribal.organization_type,
            DomainRequest.OrgChoicesElectionOffice.STATE_OR_TERRITORY_ELECTION,
        )

    @less_console_noise_decorator
    def test_create_or_update_organization_type_no_update(self):
        """Test create_or_update_organization_type when there are no values to update."""

        # Test for when both generic_org_type and organization_type is declared,
        # and are both non-election board
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=False,
        )
        domain_information = DomainInformation.create_from_dr(domain_request)
        domain_information.save()
        self.assertEqual(domain_information.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY)
        self.assertEqual(domain_information.is_election_board, False)
        self.assertEqual(domain_information.generic_org_type, DomainRequest.OrganizationChoices.CITY)

        # Test for when both generic_org_type and organization_type is declared,
        # and are both election board
        domain_request_election = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="startedElection.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=True,
            organization_type=DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION,
        )
        domain_information_election = DomainInformation.create_from_dr(domain_request_election)

        self.assertEqual(
            domain_information_election.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION
        )
        self.assertEqual(domain_information_election.is_election_board, True)
        self.assertEqual(domain_information_election.generic_org_type, DomainRequest.OrganizationChoices.CITY)

        # Modify an unrelated existing value for both, and ensure that everything is still consistent
        domain_information.city = "Fudge"
        domain_information_election.city = "Caramel"
        domain_information.save()
        domain_information_election.save()

        self.assertEqual(domain_information.city, "Fudge")
        self.assertEqual(domain_information_election.city, "Caramel")

        # Test for non-election
        self.assertEqual(domain_information.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY)
        self.assertEqual(domain_information.is_election_board, False)
        self.assertEqual(domain_information.generic_org_type, DomainRequest.OrganizationChoices.CITY)

        # Test for election
        self.assertEqual(
            domain_information_election.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION
        )
        self.assertEqual(domain_information_election.is_election_board, True)
        self.assertEqual(domain_information_election.generic_org_type, DomainRequest.OrganizationChoices.CITY)


class TestDomainRequestIncomplete(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.user = create_test_user()

    @less_console_noise_decorator
    def setUp(self):
        super().setUp()
        so, _ = Contact.objects.get_or_create(
            first_name="Meowy",
            last_name="Meoward",
            title="Chief Cat",
            email="meoward@chiefcat.com",
            phone="(206) 206 2060",
        )
        draft_domain, _ = DraftDomain.objects.get_or_create(name="MeowardMeowardMeoward.gov")
        you, _ = Contact.objects.get_or_create(
            first_name="Testy you",
            last_name="Tester you",
            title="Admin Tester",
            email="testy-admin@town.com",
            phone="(555) 555 5556",
        )
        other, _ = Contact.objects.get_or_create(
            first_name="Testy2",
            last_name="Tester2",
            title="Another Tester",
            email="testy2@town.com",
            phone="(555) 555 5557",
        )
        alt, _ = Website.objects.get_or_create(website="MeowardMeowardMeoward1.gov")
        current, _ = Website.objects.get_or_create(website="MeowardMeowardMeoward.com")
        self.amtrak, _ = FederalAgency.objects.get_or_create(agency="AMTRAK")
        self.domain_request = DomainRequest.objects.create(
            generic_org_type=DomainRequest.OrganizationChoices.FEDERAL,
            federal_type="executive",
            federal_agency=FederalAgency.objects.get(agency="AMTRAK"),
            about_your_organization="Some description",
            is_election_board=True,
            tribe_name="Some tribe name",
            organization_name="Some organization",
            address_line1="address 1",
            state_territory="CA",
            zipcode="94044",
            senior_official=so,
            requested_domain=draft_domain,
            purpose="Some purpose",
            no_other_contacts_rationale=None,
            has_cisa_representative=True,
            cisa_representative_email="somerep@cisa.com",
            has_anything_else_text=True,
            anything_else="Anything else",
            is_policy_acknowledged=True,
            requester=self.user,
            city="fake",
        )
        self.domain_request.other_contacts.add(other)
        self.domain_request.current_websites.add(current)
        self.domain_request.alternative_domains.add(alt)
        self.wizard = DomainRequestWizard()
        self.wizard._domain_request = self.domain_request
        self.wizard.request = Mock(user=self.user, session={})
        self.wizard.kwargs = {"domain_request_pk": self.domain_request.id}

    def tearDown(self):
        super().tearDown()
        DomainRequest.objects.all().delete()
        Contact.objects.all().delete()
        self.amtrak.delete()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.user.delete()

    @less_console_noise_decorator
    def test_is_federal_complete(self):
        self.assertTrue(self.wizard.form_is_complete())
        self.domain_request.federal_type = None
        self.domain_request.save()
        self.domain_request.refresh_from_db()
        self.assertFalse(self.wizard.form_is_complete())

    @less_console_noise_decorator
    def test_is_interstate_complete(self):
        self.domain_request.generic_org_type = DomainRequest.OrganizationChoices.INTERSTATE
        self.domain_request.about_your_organization = "Something something about your organization"
        self.domain_request.save()
        self.assertTrue(self.wizard.form_is_complete())
        self.domain_request.about_your_organization = None
        self.domain_request.save()
        self.assertFalse(self.wizard.form_is_complete())

    @less_console_noise_decorator
    def test_is_state_or_territory_complete(self):
        self.domain_request.generic_org_type = DomainRequest.OrganizationChoices.STATE_OR_TERRITORY
        self.domain_request.is_election_board = True
        self.domain_request.save()
        self.assertTrue(self.wizard.form_is_complete())
        self.domain_request.is_election_board = None
        self.domain_request.save()
        self.assertFalse(self.wizard.form_is_complete())

    @less_console_noise_decorator
    def test_is_tribal_complete(self):
        self.domain_request.generic_org_type = DomainRequest.OrganizationChoices.TRIBAL
        self.domain_request.tribe_name = "Tribe Name"
        self.domain_request.is_election_board = False
        self.domain_request.save()
        self.assertTrue(self.wizard.form_is_complete())
        self.domain_request.is_election_board = None
        self.domain_request.save()
        self.assertFalse(self.wizard.form_is_complete())
        self.domain_request.tribe_name = None
        self.domain_request.save()
        self.assertFalse(self.wizard.form_is_complete())

    @less_console_noise_decorator
    def test_is_county_complete(self):
        self.domain_request.generic_org_type = DomainRequest.OrganizationChoices.COUNTY
        self.domain_request.is_election_board = False
        self.domain_request.save()
        self.assertTrue(self.wizard.form_is_complete())
        self.domain_request.is_election_board = None
        self.domain_request.save()
        self.assertFalse(self.wizard.form_is_complete())

    @less_console_noise_decorator
    def test_is_city_complete(self):
        self.domain_request.generic_org_type = DomainRequest.OrganizationChoices.CITY
        self.domain_request.is_election_board = False
        self.domain_request.save()
        self.assertTrue(self.wizard.form_is_complete())
        self.domain_request.is_election_board = None
        self.domain_request.save()
        self.assertFalse(self.wizard.form_is_complete())

    @less_console_noise_decorator
    def test_is_special_district_complete(self):
        self.domain_request.generic_org_type = DomainRequest.OrganizationChoices.SPECIAL_DISTRICT
        self.domain_request.about_your_organization = "Something something about your organization"
        self.domain_request.is_election_board = False
        self.domain_request.save()
        self.assertTrue(self.wizard.form_is_complete())
        self.domain_request.is_election_board = None
        self.domain_request.save()
        self.assertFalse(self.wizard.form_is_complete())
        self.domain_request.about_your_organization = None
        self.domain_request.save()
        self.assertFalse(self.wizard.form_is_complete())

    @less_console_noise_decorator
    def test_is_organization_name_and_address_complete(self):
        self.assertTrue(self.wizard.form_is_complete())
        self.domain_request.organization_name = None
        self.domain_request.address_line1 = None
        self.domain_request.save()
        self.assertTrue(self.wizard.form_is_complete())

    @less_console_noise_decorator
    def test_is_senior_official_complete(self):
        self.assertTrue(self.wizard.form_is_complete())
        self.domain_request.senior_official = None
        self.domain_request.save()
        self.assertFalse(self.wizard.form_is_complete())

    @less_console_noise_decorator
    def test_is_requested_domain_complete(self):
        self.assertTrue(self.wizard.form_is_complete())
        self.domain_request.requested_domain = None
        self.domain_request.save()
        self.assertFalse(self.wizard.form_is_complete())

    @less_console_noise_decorator
    def test_is_purpose_complete(self):
        self.assertTrue(self.wizard.form_is_complete())
        self.domain_request.purpose = None
        self.domain_request.save()
        self.assertFalse(self.wizard.form_is_complete())

    @less_console_noise_decorator
    def test_is_other_contacts_complete_missing_one_field(self):
        self.assertTrue(self.wizard.form_is_complete())
        contact = self.domain_request.other_contacts.first()
        contact.first_name = None
        contact.save()
        self.assertFalse(self.wizard.form_is_complete())

    @less_console_noise_decorator
    def test_is_other_contacts_complete_all_none(self):
        self.domain_request.other_contacts.clear()
        self.assertFalse(self.wizard.form_is_complete())

    @less_console_noise_decorator
    def test_is_other_contacts_False_and_has_rationale(self):
        # Click radio button "No" for no other contacts and give rationale
        self.domain_request.other_contacts.clear()
        self.domain_request.other_contacts.exists = False
        self.domain_request.no_other_contacts_rationale = "Some rationale"
        self.assertTrue(self.wizard.form_is_complete())

    @less_console_noise_decorator
    def test_is_other_contacts_False_and_NO_rationale(self):
        # Click radio button "No" for no other contacts and DONT give rationale
        self.domain_request.other_contacts.clear()
        self.domain_request.other_contacts.exists = False
        self.domain_request.no_other_contacts_rationale = None
        self.assertFalse(self.wizard.form_is_complete())

    @less_console_noise_decorator
    def test_is_additional_details_complete(self):
        test_cases = [
            # CISA Rep - Yes
            # Firstname - Yes
            # Lastname - Yes
            # Email - Yes
            # Anything Else Radio - Yes
            # Anything Else Text - Yes
            {
                "has_cisa_representative": True,
                "cisa_representative_first_name": "cisa-first-name",
                "cisa_representative_last_name": "cisa-last-name",
                "cisa_representative_email": "some@cisarepemail.com",
                "has_anything_else_text": True,
                "anything_else": "Some text",
                "expected": True,
            },
            # CISA Rep - Yes
            # Firstname - Yes
            # Lastname - Yes
            # Email - Yes
            # Anything Else Radio - Yes
            # Anything Else Text - None
            {
                "has_cisa_representative": True,
                "cisa_representative_first_name": "cisa-first-name",
                "cisa_representative_last_name": "cisa-last-name",
                "cisa_representative_email": "some@cisarepemail.com",
                "has_anything_else_text": True,
                "anything_else": None,
                "expected": True,
            },
            # CISA Rep - Yes
            # Firstname - Yes
            # Lastname - Yes
            # Email - None >> e-mail is optional so it should not change anything setting this to None
            # Anything Else Radio - No
            # Anything Else Text - No
            {
                "has_cisa_representative": True,
                "cisa_representative_first_name": "cisa-first-name",
                "cisa_representative_last_name": "cisa-last-name",
                "cisa_representative_email": None,
                "has_anything_else_text": False,
                "anything_else": None,
                "expected": True,
            },
            # CISA Rep - Yes
            # Firstname - Yes
            # Lastname - Yes
            # Email - None
            # Anything Else Radio - None
            # Anything Else Text - None
            {
                "has_cisa_representative": True,
                "cisa_representative_first_name": "cisa-first-name",
                "cisa_representative_last_name": "cisa-last-name",
                "cisa_representative_email": None,
                "has_anything_else_text": None,
                "anything_else": None,
                "expected": False,
            },
            # CISA Rep - Yes
            # Firstname - None
            # Lastname - None
            # Email - None
            # Anything Else Radio - None
            # Anything Else Text - None
            {
                "has_cisa_representative": True,
                "cisa_representative_first_name": None,
                "cisa_representative_last_name": None,
                "cisa_representative_email": None,
                "has_anything_else_text": None,
                "anything_else": None,
                "expected": False,
            },
            # CISA Rep - Yes
            # Firstname - None
            # Lastname - None
            # Email - None
            # Anything Else Radio - No
            # Anything Else Text - No
            # sync_yes_no will override has_cisa_representative to be False if cisa_representative_first_name is None
            # therefore, our expected will be True
            {
                "has_cisa_representative": True,
                # Above will be overridden to False if cisa_representative_first_name is None
                "cisa_representative_first_name": None,
                "cisa_representative_last_name": None,
                "cisa_representative_email": None,
                "has_anything_else_text": False,
                "anything_else": None,
                "expected": True,
            },
            # CISA Rep - Yes
            # Firstname - None
            # Lastname - None
            # Email - None
            # Anything Else Radio - Yes
            # Anything Else Text - None
            # NOTE: We should never have an instance where only firstname or only lastname are populated
            # (they are both required)
            {
                "has_cisa_representative": True,
                # Above will be overridden to False if cisa_representative_first_name is None or
                # cisa_representative_last_name is None bc of sync_yes_no_form_fields
                "cisa_representative_first_name": None,
                "cisa_representative_last_name": None,
                "cisa_representative_email": None,
                "has_anything_else_text": True,
                "anything_else": None,
                "expected": True,
            },
            # CISA Rep - Yes
            # Firstname - None
            # Lastname - None
            # Email - None
            # Anything Else Radio - Yes
            # Anything Else Text - Yes
            {
                "has_cisa_representative": True,
                # Above will be overridden to False if cisa_representative_first_name is None or
                # cisa_representative_last_name is None bc of sync_yes_no_form_fields
                "cisa_representative_first_name": None,
                "cisa_representative_last_name": None,
                "cisa_representative_email": None,
                "has_anything_else_text": True,
                "anything_else": "Some text",
                "expected": True,
            },
            # CISA Rep - No
            # Anything Else Radio - Yes
            # Anything Else Text - Yes
            {
                "has_cisa_representative": False,
                "cisa_representative_first_name": None,
                "cisa_representative_last_name": None,
                "cisa_representative_email": None,
                "has_anything_else_text": True,
                "anything_else": "Some text",
                "expected": True,
            },
            # CISA Rep - No
            # Anything Else Radio - Yes
            # Anything Else Text - None
            {
                "has_cisa_representative": False,
                "cisa_representative_first_name": None,
                "cisa_representative_last_name": None,
                "cisa_representative_email": None,
                "has_anything_else_text": True,
                "anything_else": None,
                "expected": True,
            },
            # CISA Rep - No
            # Anything Else Radio - None
            # Anything Else Text - None
            {
                "has_cisa_representative": False,
                "cisa_representative_first_name": None,
                "cisa_representative_last_name": None,
                "cisa_representative_email": None,
                "has_anything_else_text": None,
                "anything_else": None,
                # Above is both None, so it does NOT get overwritten
                "expected": False,
            },
            # CISA Rep - No
            # Anything Else Radio - No
            # Anything Else Text - No
            {
                "has_cisa_representative": False,
                "cisa_representative_first_name": None,
                "cisa_representative_last_name": None,
                "cisa_representative_email": None,
                "has_anything_else_text": False,
                "anything_else": None,
                "expected": True,
            },
            # CISA Rep - None
            # Anything Else Radio - None
            {
                "has_cisa_representative": None,
                "cisa_representative_first_name": None,
                "cisa_representative_last_name": None,
                "cisa_representative_email": None,
                "has_anything_else_text": None,
                "anything_else": None,
                "expected": False,
            },
        ]
        for case in test_cases:
            self.domain_request.has_cisa_representative = case["has_cisa_representative"]
            self.domain_request.cisa_representative_email = case["cisa_representative_email"]
            self.domain_request.has_anything_else_text = case["has_anything_else_text"]
            self.domain_request.anything_else = case["anything_else"]
            self.domain_request.save()
            self.domain_request.refresh_from_db()
            # Compare expected test result with actual result
            result = self.wizard.form_is_complete()
            expected = case["expected"]

            if result != expected:
                self.fail(f"\nTest Failed: {case}\nExpected: {expected}, Got: {result}\n")

    @less_console_noise_decorator
    def test_is_policy_acknowledgement_complete(self):
        self.assertTrue(self.wizard.form_is_complete())
        self.domain_request.is_policy_acknowledged = False
        self.assertTrue(self.wizard.form_is_complete())
        self.domain_request.is_policy_acknowledged = None
        self.assertFalse(self.wizard.form_is_complete())

    @less_console_noise_decorator
    def test_form_complete(self):
        request = self.factory.get("/")
        request.user = self.user

        self.assertTrue(self.wizard.form_is_complete())
        self.domain_request.generic_org_type = None
        self.domain_request.save()
        self.assertFalse(self.wizard.form_is_complete())


class TestPortfolio(TestCase):
    def setUp(self):
        self.user, _ = User.objects.get_or_create(
            username="intern@igorville.com", email="intern@igorville.com", first_name="Lava", last_name="World"
        )
        self.non_federal_agency, _ = FederalAgency.objects.get_or_create(agency="Non-Federal Agency")
        self.federal_agency, _ = FederalAgency.objects.get_or_create(agency="Federal Agency")
        super().setUp()

    def tearDown(self):
        super().tearDown()
        Portfolio.objects.all().delete()
        self.federal_agency.delete()
        # not deleting non_federal_agency so as not to interfere potentially with other tests
        User.objects.all().delete()

    @less_console_noise_decorator
    def test_urbanization_field_resets_when_not_puetro_rico(self):
        """The urbanization field should only be populated when the state is puetro rico.
        Otherwise, this field should be empty."""
        # Start out as PR, then change the field
        portfolio = Portfolio.objects.create(
            requester=self.user,
            organization_name="Test Portfolio",
            state_territory=DomainRequest.StateTerritoryChoices.PUERTO_RICO,
            urbanization="test",
        )

        self.assertEqual(portfolio.urbanization, "test")
        self.assertEqual(portfolio.state_territory, DomainRequest.StateTerritoryChoices.PUERTO_RICO)

        portfolio.state_territory = DomainRequest.StateTerritoryChoices.ALABAMA
        portfolio.save()

        self.assertEqual(portfolio.urbanization, None)
        self.assertEqual(portfolio.state_territory, DomainRequest.StateTerritoryChoices.ALABAMA)

    @less_console_noise_decorator
    def test_can_add_urbanization_field(self):
        """Ensures that you can populate the urbanization field when conditions are right"""
        # Create a portfolio that cannot have this field
        portfolio = Portfolio.objects.create(
            requester=self.user,
            organization_name="Test Portfolio",
            state_territory=DomainRequest.StateTerritoryChoices.ALABAMA,
            urbanization="test",
        )

        # Implicitly check if this gets cleared on create. It should.
        self.assertEqual(portfolio.urbanization, None)
        self.assertEqual(portfolio.state_territory, DomainRequest.StateTerritoryChoices.ALABAMA)

        portfolio.state_territory = DomainRequest.StateTerritoryChoices.PUERTO_RICO
        portfolio.urbanization = "test123"
        portfolio.save()

        self.assertEqual(portfolio.urbanization, "test123")
        self.assertEqual(portfolio.state_territory, DomainRequest.StateTerritoryChoices.PUERTO_RICO)

    @less_console_noise_decorator
    def test_organization_name_updates_for_federal_agency(self):
        # Create a Portfolio instance with a federal agency
        portfolio = Portfolio(
            requester=self.user,
            organization_type=DomainRequest.OrganizationChoices.FEDERAL,
            federal_agency=self.federal_agency,
        )
        portfolio.save()

        # Assert that organization_name is updated to the federal agency's name
        self.assertEqual(portfolio.organization_name, "Federal Agency")

    @less_console_noise_decorator
    def test_organization_name_does_not_update_for_non_federal_agency(self):
        # Create a Portfolio instance with a non-federal agency
        portfolio = Portfolio(
            requester=self.user,
            organization_type=DomainRequest.OrganizationChoices.FEDERAL,
            federal_agency=self.non_federal_agency,
        )
        portfolio.save()

        # Assert that organization_name remains None
        self.assertIsNone(portfolio.organization_name)


class TestAllowedEmail(TestCase):
    """Tests our allowed email whitelist"""

    @less_console_noise_decorator
    def setUp(self):
        self.email = "mayor@igorville.gov"
        self.email_2 = "cake@igorville.gov"
        self.plus_email = "mayor+1@igorville.gov"
        self.invalid_plus_email = "1+mayor@igorville.gov"

    def tearDown(self):
        super().tearDown()
        AllowedEmail.objects.all().delete()

    def test_email_in_whitelist(self):
        """Test for a normal email defined in the whitelist"""
        AllowedEmail.objects.create(email=self.email)
        is_allowed = AllowedEmail.is_allowed_email(self.email)
        self.assertTrue(is_allowed)

    def test_email_not_in_whitelist(self):
        """Test for a normal email NOT defined in the whitelist"""
        # Check a email not in the list
        is_allowed = AllowedEmail.is_allowed_email(self.email_2)
        self.assertFalse(AllowedEmail.objects.filter(email=self.email_2).exists())
        self.assertFalse(is_allowed)

    def test_plus_email_in_whitelist(self):
        """Test for a +1 email defined in the whitelist"""
        AllowedEmail.objects.create(email=self.plus_email)
        plus_email_allowed = AllowedEmail.is_allowed_email(self.plus_email)
        self.assertTrue(plus_email_allowed)

    def test_plus_email_not_in_whitelist(self):
        """Test for a +1 email not defined in the whitelist"""
        # This email should not be allowed.
        # Checks that we do more than just a regex check on the record.
        plus_email_allowed = AllowedEmail.is_allowed_email(self.plus_email)
        self.assertFalse(plus_email_allowed)

    def test_plus_email_not_in_whitelist_but_base_email_is(self):
        """
        Test for a +1 email NOT defined in the whitelist, but the normal one is defined.
        Example:
        normal (in whitelist) - joe@igorville.com
        +1 email (not in whitelist) - joe+1@igorville.com
        """
        AllowedEmail.objects.create(email=self.email)
        base_email_allowed = AllowedEmail.is_allowed_email(self.email)
        self.assertTrue(base_email_allowed)

        # The plus email should also be allowed
        plus_email_allowed = AllowedEmail.is_allowed_email(self.plus_email)
        self.assertTrue(plus_email_allowed)

        # This email shouldn't exist in the DB
        self.assertFalse(AllowedEmail.objects.filter(email=self.plus_email).exists())

    def test_plus_email_in_whitelist_but_base_email_is_not(self):
        """
        Test for a +1 email defined in the whitelist, but the normal is NOT defined.
        Example:
        normal (not in whitelist) - joe@igorville.com
        +1 email (in whitelist) - joe+1@igorville.com
        """
        AllowedEmail.objects.create(email=self.plus_email)
        plus_email_allowed = AllowedEmail.is_allowed_email(self.plus_email)
        self.assertTrue(plus_email_allowed)

        # The base email should also be allowed
        base_email_allowed = AllowedEmail.is_allowed_email(self.email)
        self.assertTrue(base_email_allowed)

        # This email shouldn't exist in the DB
        self.assertFalse(AllowedEmail.objects.filter(email=self.email).exists())

    def test_invalid_regex_for_plus_email(self):
        """
        Test for an invalid email that contains a '+'.
        This base email should still pass, but the regex rule should not.

        Our regex should only pass for emails that end with a '+'
        Example:
        Invalid email - 1+joe@igorville.com
        Valid email: - joe+1@igorville.com
        """
        AllowedEmail.objects.create(email=self.invalid_plus_email)
        invalid_plus_email = AllowedEmail.is_allowed_email(self.invalid_plus_email)
        # We still expect that this will pass, it exists in the db
        self.assertTrue(invalid_plus_email)

        # The base email SHOULD NOT pass, as it doesn't match our regex
        base_email = AllowedEmail.is_allowed_email(self.email)
        self.assertFalse(base_email)

        # For good measure, also check the other plus email
        regular_plus_email = AllowedEmail.is_allowed_email(self.plus_email)
        self.assertFalse(regular_plus_email)
