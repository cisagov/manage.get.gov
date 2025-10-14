import unittest
from unittest.mock import patch, MagicMock, ANY
from datetime import date
from registrar.models.domain import Domain
from registrar.models.portfolio import Portfolio
from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.user import User
from registrar.models.user_domain_role import UserDomainRole
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioRoleChoices
from registrar.utility.email import EmailSendingError
from registrar.utility.email_invitations import (
    _send_portfolio_admin_addition_emails_to_portfolio_admins,
    _send_portfolio_admin_removal_emails_to_portfolio_admins,
    send_domain_invitation_email,
    _send_domain_invitation_update_emails_to_domain_managers,
    send_domain_manager_removal_emails_to_domain_managers,
    send_portfolio_admin_addition_emails,
    send_portfolio_admin_removal_emails,
    send_portfolio_invitation_email,
    send_portfolio_invitation_remove_email,
    send_portfolio_member_permission_remove_email,
    send_portfolio_member_permission_update_email,
    send_portfolio_update_emails_to_portfolio_admins,
    send_domain_manager_on_hold_email_to_domain_managers,
    send_domain_renewal_notification_emails,
)

from api.tests.common import less_console_noise_decorator
from registrar.utility.errors import MissingEmailError
from django.test import TestCase
from registrar.models import DomainInvitation


class DomainInvitationEmail(unittest.TestCase):

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.send_templated_email")
    @patch("registrar.utility.email_invitations.UserDomainRole.objects.filter")
    @patch("registrar.utility.email_invitations._validate_invitation")
    @patch("registrar.utility.email_invitations._get_requestor_email")
    @patch("registrar.utility.email_invitations._send_domain_invitation_email")
    @patch("registrar.utility.email_invitations._normalize_domains")
    def test_send_domain_invitation_email(
        self,
        mock_normalize_domains,
        mock_send_invitation_email,
        mock_get_requestor_email,
        mock_validate_invitation,
        mock_user_domain_role_filter,
        mock_send_templated_email,
    ):
        """Test sending domain invitation email for one domain.
        Should also send emails to manager of that domain.
        """
        # Setup
        mock_domain = MagicMock(name="domain1")
        mock_domain.name = "example.com"
        mock_normalize_domains.return_value = [mock_domain]

        mock_requestor = MagicMock()
        mock_requestor_email = "requestor@example.com"
        mock_get_requestor_email.return_value = mock_requestor_email

        mock_user1 = MagicMock()
        mock_user1.email = "manager1@example.com"

        mock_user_domain_role_filter.return_value = [MagicMock(user=mock_user1)]

        email = "invitee@example.com"
        is_member_of_different_org = False

        # Call the function
        send_domain_invitation_email(
            email=email,
            requestor=mock_requestor,
            domains=mock_domain,
            is_member_of_different_org=is_member_of_different_org,
        )

        # Assertions
        mock_normalize_domains.assert_called_once_with(mock_domain)
        mock_get_requestor_email.assert_called_once_with(mock_requestor, domains=[mock_domain])
        mock_validate_invitation.assert_called_once_with(
            email, None, [mock_domain], mock_requestor, is_member_of_different_org
        )
        mock_send_invitation_email.assert_called_once_with(email, mock_requestor_email, [mock_domain], None)
        mock_user_domain_role_filter.assert_called_once_with(domain=mock_domain)
        mock_send_templated_email.assert_called_once_with(
            "emails/domain_manager_notification.txt",
            "emails/domain_manager_notification_subject.txt",
            to_addresses=[mock_user1.email],
            context={
                "domain": mock_domain,
                "requestor_email": mock_requestor_email,
                "invited_email_address": email,
                "domain_manager": mock_user1,
                "date": date.today(),
            },
        )

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.send_templated_email")
    @patch("registrar.utility.email_invitations.UserDomainRole.objects.filter")
    @patch("registrar.utility.email_invitations._validate_invitation")
    @patch("registrar.utility.email_invitations._get_requestor_email")
    @patch("registrar.utility.email_invitations._send_domain_invitation_email")
    @patch("registrar.utility.email_invitations._normalize_domains")
    def test_send_domain_invitation_email_multiple_domains(
        self,
        mock_normalize_domains,
        mock_send_invitation_email,
        mock_get_requestor_email,
        mock_validate_invitation,
        mock_user_domain_role_filter,
        mock_send_templated_email,
    ):
        """Test sending domain invitation email for multiple domains.
        Should also send emails to managers of each domain.
        """
        # Setup
        # Create multiple mock domains
        mock_domain1 = MagicMock(name="domain1")
        mock_domain1.name = "example.com"
        mock_domain2 = MagicMock(name="domain2")
        mock_domain2.name = "example.org"

        mock_normalize_domains.return_value = [mock_domain1, mock_domain2]

        mock_requestor = MagicMock()
        mock_requestor_email = "requestor@example.com"
        mock_get_requestor_email.return_value = mock_requestor_email

        mock_user1 = MagicMock()
        mock_user1.email = "manager1@example.com"
        mock_user2 = MagicMock()
        mock_user2.email = "manager2@example.com"

        # Configure domain roles for each domain
        def filter_side_effect(domain):
            if domain == mock_domain1:
                return [MagicMock(user=mock_user1)]
            elif domain == mock_domain2:
                return [MagicMock(user=mock_user2)]
            return []

        mock_user_domain_role_filter.side_effect = filter_side_effect

        email = "invitee@example.com"
        is_member_of_different_org = False

        # Call the function
        send_domain_invitation_email(
            email=email,
            requestor=mock_requestor,
            domains=[mock_domain1, mock_domain2],
            is_member_of_different_org=is_member_of_different_org,
        )

        # Assertions
        mock_normalize_domains.assert_called_once_with([mock_domain1, mock_domain2])
        mock_get_requestor_email.assert_called_once_with(mock_requestor, domains=[mock_domain1, mock_domain2])
        mock_validate_invitation.assert_called_once_with(
            email, None, [mock_domain1, mock_domain2], mock_requestor, is_member_of_different_org
        )
        mock_send_invitation_email.assert_called_once_with(
            email, mock_requestor_email, [mock_domain1, mock_domain2], None
        )

        # Check that domain manager emails were sent for both domains
        mock_user_domain_role_filter.assert_any_call(domain=mock_domain1)
        mock_user_domain_role_filter.assert_any_call(domain=mock_domain2)

        mock_send_templated_email.assert_any_call(
            "emails/domain_manager_notification.txt",
            "emails/domain_manager_notification_subject.txt",
            to_addresses=[mock_user1.email],
            context={
                "domain": mock_domain1,
                "requestor_email": mock_requestor_email,
                "invited_email_address": email,
                "domain_manager": mock_user1,
                "date": date.today(),
            },
        )
        mock_send_templated_email.assert_any_call(
            "emails/domain_manager_notification.txt",
            "emails/domain_manager_notification_subject.txt",
            to_addresses=[mock_user2.email],
            context={
                "domain": mock_domain2,
                "requestor_email": mock_requestor_email,
                "invited_email_address": email,
                "domain_manager": mock_user2,
                "date": date.today(),
            },
        )

        # Verify the total number of calls to send_templated_email
        self.assertEqual(mock_send_templated_email.call_count, 2)

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations._validate_invitation")
    def test_send_domain_invitation_email_raises_invite_validation_exception(self, mock_validate_invitation):
        """Test sending domain invitation email for one domain and assert exception
        when invite validation fails.
        """
        # Setup
        mock_validate_invitation.side_effect = ValueError("Validation failed")
        email = "invitee@example.com"
        requestor = MagicMock()
        domain = MagicMock()

        # Call and assert exception
        with self.assertRaises(ValueError) as context:
            send_domain_invitation_email(email, requestor, domain, is_member_of_different_org=False)

        self.assertEqual(str(context.exception), "Validation failed")
        mock_validate_invitation.assert_called_once()

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations._get_requestor_email")
    def test_send_domain_invitation_email_raises_get_requestor_email_exception(self, mock_get_requestor_email):
        """Test sending domain invitation email for one domain and assert exception
        when get_requestor_email fails.
        """
        # Setup
        mock_get_requestor_email.side_effect = ValueError("Validation failed")
        email = "invitee@example.com"
        requestor = MagicMock()
        domain = MagicMock()

        # Call and assert exception
        with self.assertRaises(ValueError) as context:
            send_domain_invitation_email(email, requestor, domain, is_member_of_different_org=False)

        self.assertEqual(str(context.exception), "Validation failed")
        mock_get_requestor_email.assert_called_once()

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations._validate_invitation")
    @patch("registrar.utility.email_invitations._get_requestor_email")
    @patch("registrar.utility.email_invitations._send_domain_invitation_email")
    @patch("registrar.utility.email_invitations._normalize_domains")
    def test_send_domain_invitation_email_raises_sending_email_exception(
        self,
        mock_normalize_domains,
        mock_send_invitation_email,
        mock_get_requestor_email,
        mock_validate_invitation,
    ):
        """Test sending domain invitation email for one domain and assert exception
        when send_invitation_email fails.
        """
        # Setup
        mock_domain = MagicMock(name="domain1")
        mock_domain.name = "example.com"
        mock_normalize_domains.return_value = [mock_domain]

        mock_requestor = MagicMock()
        mock_requestor_email = "requestor@example.com"
        mock_get_requestor_email.return_value = mock_requestor_email

        mock_user1 = MagicMock()
        mock_user1.email = "manager1@example.com"

        email = "invitee@example.com"
        is_member_of_different_org = False

        mock_send_invitation_email.side_effect = EmailSendingError("Error sending email")

        # Call and assert exception
        with self.assertRaises(EmailSendingError) as context:
            send_domain_invitation_email(
                email=email,
                requestor=mock_requestor,
                domains=mock_domain,
                is_member_of_different_org=is_member_of_different_org,
            )

        # Assertions
        mock_normalize_domains.assert_called_once_with(mock_domain)
        mock_get_requestor_email.assert_called_once_with(mock_requestor, domains=[mock_domain])
        mock_validate_invitation.assert_called_once_with(
            email, None, [mock_domain], mock_requestor, is_member_of_different_org
        )
        self.assertEqual(str(context.exception), "Error sending email")

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations._send_domain_invitation_update_emails_to_domain_managers")
    @patch("registrar.utility.email_invitations._validate_invitation")
    @patch("registrar.utility.email_invitations._get_requestor_email")
    @patch("registrar.utility.email_invitations._send_domain_invitation_email")
    @patch("registrar.utility.email_invitations._normalize_domains")
    def test_send_domain_invitation_email_manager_emails_send_mail_exception(
        self,
        mock_normalize_domains,
        mock_send_invitation_email,
        mock_get_requestor_email,
        mock_validate_invitation,
        mock_send_domain_manager_emails,
    ):
        """Test sending domain invitation email for one domain and assert exception
        when _send_domain_invitation_update_emails_to_domain_managers fails.
        """
        # Setup
        mock_domain = MagicMock(name="domain1")
        mock_domain.name = "example.com"
        mock_normalize_domains.return_value = [mock_domain]

        mock_requestor = MagicMock()
        mock_requestor_email = "requestor@example.com"
        mock_get_requestor_email.return_value = mock_requestor_email

        email = "invitee@example.com"
        is_member_of_different_org = False

        # Change the return value to False for mock_send_domain_manager_emails
        mock_send_domain_manager_emails.return_value = False

        # Call and assert that send_domain_invitation_email returns False
        result = send_domain_invitation_email(
            email=email,
            requestor=mock_requestor,
            domains=mock_domain,
            is_member_of_different_org=is_member_of_different_org,
        )

        # Assertions
        mock_normalize_domains.assert_called_once_with(mock_domain)
        mock_get_requestor_email.assert_called_once_with(mock_requestor, domains=[mock_domain])
        mock_validate_invitation.assert_called_once_with(
            email, None, [mock_domain], mock_requestor, is_member_of_different_org
        )
        mock_send_invitation_email.assert_called_once_with(email, mock_requestor_email, [mock_domain], None)

        # Assert that the result is False
        self.assertFalse(result)

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.send_templated_email")
    @patch("registrar.models.UserDomainRole.objects.filter")
    def test_send_emails_to_domain_managers_all_emails_sent_successfully(self, mock_filter, mock_send_templated_email):
        """Test when all emails are sent successfully."""

        # Setup mocks
        mock_domain = MagicMock(spec=Domain)
        mock_requestor_email = "requestor@example.com"
        mock_email = "invitee@example.com"

        # Create mock user and UserDomainRole
        mock_user = MagicMock(spec=User)
        mock_user.email = "manager@example.com"
        mock_user_domain_role = MagicMock(spec=UserDomainRole, user=mock_user)

        # Mock the filter method to return a list of mock UserDomainRole objects
        mock_filter.return_value = [mock_user_domain_role]

        # Mock successful email sending
        mock_send_templated_email.return_value = None  # No exception means success

        # Call function
        result = _send_domain_invitation_update_emails_to_domain_managers(mock_email, mock_requestor_email, mock_domain)

        # Assertions
        self.assertTrue(result)  # All emails should be successfully sent
        mock_send_templated_email.assert_called_once_with(
            "emails/domain_manager_notification.txt",
            "emails/domain_manager_notification_subject.txt",
            to_addresses=["manager@example.com"],
            context={
                "domain": mock_domain,
                "requestor_email": mock_requestor_email,
                "invited_email_address": mock_email,
                "domain_manager": mock_user,
                "date": date.today(),
            },
        )

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.send_templated_email")
    @patch("registrar.models.UserDomainRole.objects.filter")
    def test_send_emails_to_domain_managers_email_send_fails(self, mock_filter, mock_send_templated_email):
        """Test when sending an email fails (raises EmailSendingError)."""

        # Setup mocks
        mock_domain = MagicMock(spec=Domain)
        mock_requestor_email = "requestor@example.com"
        mock_email = "invitee@example.com"

        # Create mock user and UserDomainRole
        mock_user = MagicMock(spec=User)
        mock_user.email = "manager@example.com"
        mock_user_domain_role = MagicMock(spec=UserDomainRole, user=mock_user)

        # Mock the filter method to return a list of mock UserDomainRole objects
        mock_filter.return_value = [mock_user_domain_role]

        # Mock sending email to raise an EmailSendingError
        mock_send_templated_email.side_effect = EmailSendingError("Email sending failed")

        # Call function
        result = _send_domain_invitation_update_emails_to_domain_managers(mock_email, mock_requestor_email, mock_domain)

        # Assertions
        self.assertFalse(result)  # The result should be False as email sending failed
        mock_send_templated_email.assert_called_once_with(
            "emails/domain_manager_notification.txt",
            "emails/domain_manager_notification_subject.txt",
            to_addresses=["manager@example.com"],
            context={
                "domain": mock_domain,
                "requestor_email": mock_requestor_email,
                "invited_email_address": mock_email,
                "domain_manager": mock_user,
                "date": date.today(),
            },
        )

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.send_templated_email")
    @patch("registrar.models.UserDomainRole.objects.filter")
    def test_send_emails_to_domain_managers_no_domain_managers(self, mock_filter, mock_send_templated_email):
        """Test when there are no domain managers."""

        # Setup mocks
        mock_domain = MagicMock(spec=Domain)
        mock_requestor_email = "requestor@example.com"
        mock_email = "invitee@example.com"

        # Mock no domain managers (empty UserDomainRole queryset)
        mock_filter.return_value = []

        # Call function
        result = _send_domain_invitation_update_emails_to_domain_managers(mock_email, mock_requestor_email, mock_domain)

        # Assertions
        self.assertTrue(result)  # No emails to send, so it should return True
        mock_send_templated_email.assert_not_called()  # No emails should be sent

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.send_templated_email")
    @patch("registrar.models.UserDomainRole.objects.filter")
    def test_send_emails_to_domain_managers_some_emails_fail(self, mock_filter, mock_send_templated_email):
        """Test when some emails fail to send."""

        # Setup mocks
        mock_domain = MagicMock(spec=Domain)
        mock_requestor_email = "requestor@example.com"
        mock_email = "invitee@example.com"

        # Create mock users and UserDomainRoles
        mock_user_1 = MagicMock(spec=User)
        mock_user_1.email = "manager1@example.com"
        mock_user_2 = MagicMock(spec=User)
        mock_user_2.email = "manager2@example.com"

        mock_user_domain_role_1 = MagicMock(spec=UserDomainRole, user=mock_user_1)
        mock_user_domain_role_2 = MagicMock(spec=UserDomainRole, user=mock_user_2)
        mock_filter.return_value = [mock_user_domain_role_1, mock_user_domain_role_2]

        # Mock first email success and second email failure
        mock_send_templated_email.side_effect = [None, EmailSendingError("Failed to send email")]

        # Call function
        result = _send_domain_invitation_update_emails_to_domain_managers(mock_email, mock_requestor_email, mock_domain)

        # Assertions
        self.assertFalse(result)  # One email failed, so result should be False
        mock_send_templated_email.assert_any_call(
            "emails/domain_manager_notification.txt",
            "emails/domain_manager_notification_subject.txt",
            to_addresses=["manager1@example.com"],
            context={
                "domain": mock_domain,
                "requestor_email": mock_requestor_email,
                "invited_email_address": mock_email,
                "domain_manager": mock_user_1,
                "date": date.today(),
            },
        )
        mock_send_templated_email.assert_any_call(
            "emails/domain_manager_notification.txt",
            "emails/domain_manager_notification_subject.txt",
            to_addresses=["manager2@example.com"],
            context={
                "domain": mock_domain,
                "requestor_email": mock_requestor_email,
                "invited_email_address": mock_email,
                "domain_manager": mock_user_2,
                "date": date.today(),
            },
        )


class PortfolioInvitationEmailTests(unittest.TestCase):

    def setUp(self):
        """Setup common test data for all test cases"""
        self.email = "invitee@example.com"
        self.requestor = MagicMock(name="User")
        self.requestor.email = "requestor@example.com"
        self.portfolio = MagicMock(name="Portfolio")

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.send_templated_email")
    def test_send_portfolio_invitation_email_success(self, mock_send_templated_email):
        """Test successful email sending"""
        is_admin_invitation = False

        result = send_portfolio_invitation_email(self.email, self.requestor, self.portfolio, is_admin_invitation)

        self.assertTrue(result)
        mock_send_templated_email.assert_called_once()

    @less_console_noise_decorator
    @patch(
        "registrar.utility.email_invitations.send_templated_email",
        side_effect=EmailSendingError("Failed to send email"),
    )
    def test_send_portfolio_invitation_email_failure(self, mock_send_templated_email):
        """Test failure when sending email"""
        is_admin_invitation = False

        with self.assertRaises(EmailSendingError) as context:
            send_portfolio_invitation_email(self.email, self.requestor, self.portfolio, is_admin_invitation)

        self.assertIn("Could not sent email invitation to", str(context.exception))

    @less_console_noise_decorator
    @patch(
        "registrar.utility.email_invitations._get_requestor_email",
        side_effect=MissingEmailError("Requestor has no email"),
    )
    def test_send_portfolio_invitation_email_missing_requestor_email(self, mock_get_email):
        """Test when requestor has no email"""
        is_admin_invitation = False

        with self.assertRaises(MissingEmailError) as context:
            send_portfolio_invitation_email(self.email, self.requestor, self.portfolio, is_admin_invitation)

        self.assertIn(
            "Can't send invitation email. No email is associated with your user account.", str(context.exception)
        )

    @less_console_noise_decorator
    @patch(
        "registrar.utility.email_invitations._send_portfolio_admin_addition_emails_to_portfolio_admins",
        return_value=False,
    )
    @patch("registrar.utility.email_invitations.send_templated_email")
    def test_send_portfolio_invitation_email_admin_invitation(self, mock_send_templated_email, mock_admin_email):
        """Test admin invitation email logic"""
        is_admin_invitation = True

        result = send_portfolio_invitation_email(self.email, self.requestor, self.portfolio, is_admin_invitation)

        self.assertFalse(result)  # Admin email sending failed
        mock_send_templated_email.assert_called_once()
        mock_admin_email.assert_called_once()

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations._get_requestor_email")
    @patch("registrar.utility.email_invitations._send_portfolio_admin_addition_emails_to_portfolio_admins")
    def test_send_email_success(self, mock_send_admin_emails, mock_get_requestor_email):
        """Test successful sending of admin addition emails."""
        mock_get_requestor_email.return_value = "requestor@example.com"
        mock_send_admin_emails.return_value = True

        result = send_portfolio_admin_addition_emails(self.email, self.requestor, self.portfolio)

        mock_get_requestor_email.assert_called_once_with(self.requestor, portfolio=self.portfolio)
        mock_send_admin_emails.assert_called_once_with(self.email, "requestor@example.com", self.portfolio)
        self.assertTrue(result)

    @less_console_noise_decorator
    @patch(
        "registrar.utility.email_invitations._get_requestor_email",
        side_effect=MissingEmailError("Requestor email missing"),
    )
    def test_missing_requestor_email_raises_exception(self, mock_get_requestor_email):
        """Test exception raised if requestor email is missing."""
        with self.assertRaises(MissingEmailError):
            send_portfolio_admin_addition_emails(self.email, self.requestor, self.portfolio)

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations._get_requestor_email")
    @patch("registrar.utility.email_invitations._send_portfolio_admin_addition_emails_to_portfolio_admins")
    def test_send_email_failure(self, mock_send_admin_emails, mock_get_requestor_email):
        """Test handling of failure in sending admin addition emails."""
        mock_get_requestor_email.return_value = "requestor@example.com"
        mock_send_admin_emails.return_value = False  # Simulate failure

        result = send_portfolio_admin_addition_emails(self.email, self.requestor, self.portfolio)

        self.assertFalse(result)
        mock_get_requestor_email.assert_called_once_with(self.requestor, portfolio=self.portfolio)
        mock_send_admin_emails.assert_called_once_with(self.email, "requestor@example.com", self.portfolio)


class SendPortfolioAdminAdditionEmailsTests(unittest.TestCase):
    """Unit tests for _send_portfolio_admin_addition_emails_to_portfolio_admins function."""

    def setUp(self):
        """Set up test data."""
        self.email = "new.admin@example.com"
        self.requestor_email = "requestor@example.com"
        self.portfolio = MagicMock(spec=Portfolio)
        self.portfolio.organization_name = "Test Organization"

        # Mock portfolio admin users
        self.admin_user1 = MagicMock(spec=User)
        self.admin_user1.email = "admin1@example.com"

        self.admin_user2 = MagicMock(spec=User)
        self.admin_user2.email = "admin2@example.com"

        self.portfolio_admin1 = MagicMock(spec=UserPortfolioPermission)
        self.portfolio_admin1.user = self.admin_user1
        self.portfolio_admin1.roles = [UserPortfolioRoleChoices.ORGANIZATION_ADMIN]

        self.portfolio_admin2 = MagicMock(spec=UserPortfolioPermission)
        self.portfolio_admin2.user = self.admin_user2
        self.portfolio_admin2.roles = [UserPortfolioRoleChoices.ORGANIZATION_ADMIN]

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.send_templated_email")
    @patch("registrar.utility.email_invitations.UserPortfolioPermission.objects.filter")
    def test_send_email_success(self, mock_filter, mock_send_templated_email):
        """Test successful sending of admin addition emails."""
        mock_filter.return_value.exclude.return_value = [self.portfolio_admin1, self.portfolio_admin2]
        mock_send_templated_email.return_value = None  # No exception means success

        result = _send_portfolio_admin_addition_emails_to_portfolio_admins(
            self.email, self.requestor_email, self.portfolio
        )

        mock_filter.assert_called_once_with(
            portfolio=self.portfolio, roles__contains=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )
        mock_send_templated_email.assert_any_call(
            "emails/portfolio_admin_addition_notification.txt",
            "emails/portfolio_admin_addition_notification_subject.txt",
            to_addresses=[self.admin_user1.email],
            context={
                "portfolio": self.portfolio,
                "requestor_email": self.requestor_email,
                "invited_email_address": self.email,
                "portfolio_admin": self.admin_user1,
                "date": date.today(),
            },
        )
        mock_send_templated_email.assert_any_call(
            "emails/portfolio_admin_addition_notification.txt",
            "emails/portfolio_admin_addition_notification_subject.txt",
            to_addresses=[self.admin_user2.email],
            context={
                "portfolio": self.portfolio,
                "requestor_email": self.requestor_email,
                "invited_email_address": self.email,
                "portfolio_admin": self.admin_user2,
                "date": date.today(),
            },
        )
        self.assertTrue(result)

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.send_templated_email", side_effect=EmailSendingError)
    @patch("registrar.utility.email_invitations.UserPortfolioPermission.objects.filter")
    def test_send_email_failure(self, mock_filter, mock_send_templated_email):
        """Test handling of failure in sending admin addition emails."""
        mock_filter.return_value.exclude.return_value = [self.portfolio_admin1, self.portfolio_admin2]

        result = _send_portfolio_admin_addition_emails_to_portfolio_admins(
            self.email, self.requestor_email, self.portfolio
        )

        self.assertFalse(result)
        mock_filter.assert_called_once_with(
            portfolio=self.portfolio, roles__contains=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )
        mock_send_templated_email.assert_any_call(
            "emails/portfolio_admin_addition_notification.txt",
            "emails/portfolio_admin_addition_notification_subject.txt",
            to_addresses=[self.admin_user1.email],
            context={
                "portfolio": self.portfolio,
                "requestor_email": self.requestor_email,
                "invited_email_address": self.email,
                "portfolio_admin": self.admin_user1,
                "date": date.today(),
            },
        )
        mock_send_templated_email.assert_any_call(
            "emails/portfolio_admin_addition_notification.txt",
            "emails/portfolio_admin_addition_notification_subject.txt",
            to_addresses=[self.admin_user2.email],
            context={
                "portfolio": self.portfolio,
                "requestor_email": self.requestor_email,
                "invited_email_address": self.email,
                "portfolio_admin": self.admin_user2,
                "date": date.today(),
            },
        )

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.UserPortfolioPermission.objects.filter")
    def test_no_admins_to_notify(self, mock_filter):
        """Test case where there are no portfolio admins to notify."""
        mock_filter.return_value.exclude.return_value = []  # No admins

        result = _send_portfolio_admin_addition_emails_to_portfolio_admins(
            self.email, self.requestor_email, self.portfolio
        )

        self.assertTrue(result)  # No emails sent, but also no failures
        mock_filter.assert_called_once_with(
            portfolio=self.portfolio, roles__contains=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )


class SendPortfolioAdminRemovalEmailsToAdminsTests(unittest.TestCase):
    """Unit tests for _send_portfolio_admin_removal_emails_to_portfolio_admins function."""

    def setUp(self):
        """Set up test data."""
        self.email = "removed.admin@example.com"
        self.requestor_email = "requestor@example.com"
        self.portfolio = MagicMock(spec=Portfolio)
        self.portfolio.organization_name = "Test Organization"

        # Mock portfolio admin users
        self.admin_user1 = MagicMock(spec=User)
        self.admin_user1.email = "admin1@example.com"

        self.admin_user2 = MagicMock(spec=User)
        self.admin_user2.email = "admin2@example.com"

        self.portfolio_admin1 = MagicMock(spec=UserPortfolioPermission)
        self.portfolio_admin1.user = self.admin_user1
        self.portfolio_admin1.roles = [UserPortfolioRoleChoices.ORGANIZATION_ADMIN]

        self.portfolio_admin2 = MagicMock(spec=UserPortfolioPermission)
        self.portfolio_admin2.user = self.admin_user2
        self.portfolio_admin2.roles = [UserPortfolioRoleChoices.ORGANIZATION_ADMIN]

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.send_templated_email")
    @patch("registrar.utility.email_invitations.UserPortfolioPermission.objects.filter")
    def test_send_email_success(self, mock_filter, mock_send_templated_email):
        """Test successful sending of admin removal emails."""
        mock_filter.return_value.exclude.return_value = [self.portfolio_admin1, self.portfolio_admin2]
        mock_send_templated_email.return_value = None  # No exception means success

        result = _send_portfolio_admin_removal_emails_to_portfolio_admins(
            self.email, self.requestor_email, self.portfolio
        )

        mock_filter.assert_called_once_with(
            portfolio=self.portfolio, roles__contains=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )
        mock_send_templated_email.assert_any_call(
            "emails/portfolio_admin_removal_notification.txt",
            "emails/portfolio_admin_removal_notification_subject.txt",
            to_addresses=[self.admin_user1.email],
            context={
                "portfolio": self.portfolio,
                "requestor_email": self.requestor_email,
                "removed_email_address": self.email,
                "portfolio_admin": self.admin_user1,
                "date": date.today(),
            },
        )
        mock_send_templated_email.assert_any_call(
            "emails/portfolio_admin_removal_notification.txt",
            "emails/portfolio_admin_removal_notification_subject.txt",
            to_addresses=[self.admin_user2.email],
            context={
                "portfolio": self.portfolio,
                "requestor_email": self.requestor_email,
                "removed_email_address": self.email,
                "portfolio_admin": self.admin_user2,
                "date": date.today(),
            },
        )
        self.assertTrue(result)

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.send_templated_email", side_effect=EmailSendingError)
    @patch("registrar.utility.email_invitations.UserPortfolioPermission.objects.filter")
    def test_send_email_failure(self, mock_filter, mock_send_templated_email):
        """Test handling of failure in sending admin removal emails."""
        mock_filter.return_value.exclude.return_value = [self.portfolio_admin1, self.portfolio_admin2]

        result = _send_portfolio_admin_removal_emails_to_portfolio_admins(
            self.email, self.requestor_email, self.portfolio
        )

        self.assertFalse(result)
        mock_filter.assert_called_once_with(
            portfolio=self.portfolio, roles__contains=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )
        mock_send_templated_email.assert_any_call(
            "emails/portfolio_admin_removal_notification.txt",
            "emails/portfolio_admin_removal_notification_subject.txt",
            to_addresses=[self.admin_user1.email],
            context={
                "portfolio": self.portfolio,
                "requestor_email": self.requestor_email,
                "removed_email_address": self.email,
                "portfolio_admin": self.admin_user1,
                "date": date.today(),
            },
        )
        mock_send_templated_email.assert_any_call(
            "emails/portfolio_admin_removal_notification.txt",
            "emails/portfolio_admin_removal_notification_subject.txt",
            to_addresses=[self.admin_user2.email],
            context={
                "portfolio": self.portfolio,
                "requestor_email": self.requestor_email,
                "removed_email_address": self.email,
                "portfolio_admin": self.admin_user2,
                "date": date.today(),
            },
        )

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.UserPortfolioPermission.objects.filter")
    def test_no_admins_to_notify(self, mock_filter):
        """Test case where there are no portfolio admins to notify."""
        mock_filter.return_value.exclude.return_value = []  # No admins

        result = _send_portfolio_admin_removal_emails_to_portfolio_admins(
            self.email, self.requestor_email, self.portfolio
        )

        self.assertTrue(result)  # No emails sent, but also no failures
        mock_filter.assert_called_once_with(
            portfolio=self.portfolio, roles__contains=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )


class SendPortfolioAdminRemovalEmailsTests(unittest.TestCase):
    """Unit tests for send_portfolio_admin_removal_emails function."""

    def setUp(self):
        """Set up test data."""
        self.email = "removed.admin@example.com"
        self.requestor = MagicMock(spec=User)
        self.requestor.email = "requestor@example.com"
        self.portfolio = MagicMock(spec=Portfolio)
        self.portfolio.organization_name = "Test Organization"

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations._get_requestor_email")
    @patch("registrar.utility.email_invitations._send_portfolio_admin_removal_emails_to_portfolio_admins")
    def test_send_email_success(self, mock_send_removal_emails, mock_get_requestor_email):
        """Test successful execution of send_portfolio_admin_removal_emails."""
        mock_get_requestor_email.return_value = self.requestor.email
        mock_send_removal_emails.return_value = True  # Simulating success

        result = send_portfolio_admin_removal_emails(self.email, self.requestor, self.portfolio)

        mock_get_requestor_email.assert_called_once_with(self.requestor, portfolio=self.portfolio)
        mock_send_removal_emails.assert_called_once_with(self.email, self.requestor.email, self.portfolio)
        self.assertTrue(result)

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations._get_requestor_email", side_effect=MissingEmailError("No email found"))
    @patch("registrar.utility.email_invitations._send_portfolio_admin_removal_emails_to_portfolio_admins")
    def test_missing_email_error(self, mock_send_removal_emails, mock_get_requestor_email):
        """Test handling of MissingEmailError when requestor has no email."""
        with self.assertRaises(MissingEmailError) as context:
            send_portfolio_admin_removal_emails(self.email, self.requestor, self.portfolio)

        mock_get_requestor_email.assert_called_once_with(self.requestor, portfolio=self.portfolio)
        mock_send_removal_emails.assert_not_called()  # Should not proceed if email retrieval fails
        self.assertEqual(
            str(context.exception), "Can't send invitation email. No email is associated with your user account."
        )

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations._get_requestor_email")
    @patch(
        "registrar.utility.email_invitations._send_portfolio_admin_removal_emails_to_portfolio_admins",
        return_value=False,
    )
    def test_send_email_failure(self, mock_send_removal_emails, mock_get_requestor_email):
        """Test handling of failure when admin removal emails fail to send."""
        mock_get_requestor_email.return_value = self.requestor.email
        mock_send_removal_emails.return_value = False  # Simulating failure

        result = send_portfolio_admin_removal_emails(self.email, self.requestor, self.portfolio)

        mock_get_requestor_email.assert_called_once_with(self.requestor, portfolio=self.portfolio)
        mock_send_removal_emails.assert_called_once_with(self.email, self.requestor.email, self.portfolio)
        self.assertFalse(result)


class TestSendPortfolioMemberPermissionUpdateEmail(unittest.TestCase):
    """Unit tests for send_portfolio_member_permission_update_email function."""

    @patch("registrar.utility.email_invitations.send_templated_email")
    @patch("registrar.utility.email_invitations._get_requestor_email")
    def test_send_email_success(self, mock_get_requestor_email, mock_send_email):
        """Test that the email is sent successfully when there are no errors."""
        # Mock data
        requestor = MagicMock()
        permissions = MagicMock(spec=UserPortfolioPermission)
        permissions.user.email = "user@example.com"
        permissions.portfolio.organization_name = "Test Portfolio"

        mock_get_requestor_email.return_value = "requestor@example.com"

        # Call function
        result = send_portfolio_member_permission_update_email(requestor, permissions)

        # Assertions
        mock_get_requestor_email.assert_called_once_with(requestor, portfolio=permissions.portfolio)
        mock_send_email.assert_called_once_with(
            "emails/portfolio_update.txt",
            "emails/portfolio_update_subject.txt",
            to_addresses=["user@example.com"],
            context={
                "requested_user": permissions.user,
                "portfolio": permissions.portfolio,
                "requestor_email": "requestor@example.com",
                "permissions": permissions,
                "date": date.today(),
            },
        )
        self.assertTrue(result)

    @patch("registrar.utility.email_invitations.send_templated_email", side_effect=EmailSendingError("Email failed"))
    @patch("registrar.utility.email_invitations._get_requestor_email")
    @patch("registrar.utility.email_invitations.logger")
    def test_send_email_failure(self, mock_logger, mock_get_requestor_email, mock_send_email):
        """Test that the function returns False and logs an error when email sending fails."""
        # Mock data
        requestor = MagicMock()
        permissions = MagicMock(spec=UserPortfolioPermission)
        permissions.user.email = "user@example.com"
        permissions.portfolio.organization_name = "Test Portfolio"

        mock_get_requestor_email.return_value = MagicMock(name="mock.email")

        # Call function
        result = send_portfolio_member_permission_update_email(requestor, permissions)

        # Assertions
        expected_message = (
            "Failed to send organization member update notification email:\n"
            f"  Requestor Email: {mock_get_requestor_email.return_value}\n"
            f"  Subject template: portfolio_update_subject.txt\n"
            f"  To: {permissions.user.email}\n"
            f"  Portfolio: {permissions.portfolio}\n"
            f"  Error: Email failed"
        )

        mock_logger.error.assert_called_once_with(expected_message, exc_info=True)
        self.assertFalse(result)

    @patch("registrar.utility.email_invitations._get_requestor_email", side_effect=Exception("Unexpected error"))
    @patch("registrar.utility.email_invitations.logger")
    def test_requestor_email_retrieval_failure(self, mock_logger, mock_get_requestor_email):
        """Test that an exception in retrieving requestor email is logged."""
        # Mock data
        requestor = MagicMock()
        permissions = MagicMock(spec=UserPortfolioPermission)

        # Call function
        with self.assertRaises(Exception):
            send_portfolio_member_permission_update_email(requestor, permissions)

        # Assertions
        mock_logger.warning.assert_not_called()  # Function should fail before logging email failure


class TestSendPortfolioMemberPermissionRemoveEmail(unittest.TestCase):
    """Unit tests for send_portfolio_member_permission_remove_email function."""

    @patch("registrar.utility.email_invitations.send_templated_email")
    @patch("registrar.utility.email_invitations._get_requestor_email")
    def test_send_email_success(self, mock_get_requestor_email, mock_send_email):
        """Test that the email is sent successfully when there are no errors."""
        # Mock data
        requestor = MagicMock()
        permissions = MagicMock(spec=UserPortfolioPermission)
        permissions.user.email = "user@example.com"
        permissions.portfolio.organization_name = "Test Portfolio"

        mock_get_requestor_email.return_value = "requestor@example.com"

        # Call function
        result = send_portfolio_member_permission_remove_email(requestor, permissions)

        # Assertions
        mock_get_requestor_email.assert_called_once_with(requestor, portfolio=permissions.portfolio)
        mock_send_email.assert_called_once_with(
            "emails/portfolio_removal.txt",
            "emails/portfolio_removal_subject.txt",
            to_addresses=["user@example.com"],
            context={
                "requested_user": permissions.user,
                "portfolio": permissions.portfolio,
                "requestor_email": "requestor@example.com",
            },
        )
        self.assertTrue(result)

    @patch("registrar.utility.email_invitations.send_templated_email", side_effect=EmailSendingError("Email failed"))
    @patch("registrar.utility.email_invitations._get_requestor_email")
    @patch("registrar.utility.email_invitations.logger")
    def test_send_email_failure(self, mock_logger, mock_get_requestor_email, mock_send_email):
        """Test that the function returns False and logs an error when email sending fails."""
        # Mock data
        requestor = MagicMock()
        permissions = MagicMock(spec=UserPortfolioPermission)
        permissions.user.email = "user@example.com"
        permissions.portfolio.organization_name = "Test Portfolio"

        mock_get_requestor_email.return_value = MagicMock(name="mock.email")

        # Call function
        result = send_portfolio_member_permission_remove_email(requestor, permissions)

        # Assertions
        expected_message = (
            "Failed to send portfolio member removal email:\n"
            f"  Requestor Email: {mock_get_requestor_email.return_value}\n"
            f"  Subject template: portfolio_removal_subject.txt\n"
            f"  To: {permissions.user.email}\n"
            f"  Portfolio: {permissions.portfolio}\n"
            f"  Error: Email failed"
        )

        mock_logger.error.assert_called_once_with(expected_message, exc_info=True)
        self.assertFalse(result)

    @patch("registrar.utility.email_invitations._get_requestor_email", side_effect=Exception("Unexpected error"))
    @patch("registrar.utility.email_invitations.logger")
    def test_requestor_email_retrieval_failure(self, mock_logger, mock_get_requestor_email):
        """Test that an exception in retrieving requestor email is logged."""
        # Mock data
        requestor = MagicMock()
        permissions = MagicMock(spec=UserPortfolioPermission)

        # Call function
        with self.assertRaises(Exception):
            send_portfolio_member_permission_remove_email(requestor, permissions)

        # Assertions
        mock_logger.warning.assert_not_called()  # Function should fail before logging email failure


class TestSendPortfolioInvitationRemoveEmail(unittest.TestCase):
    """Unit tests for send_portfolio_invitation_remove_email function."""

    @patch("registrar.utility.email_invitations.send_templated_email")
    @patch("registrar.utility.email_invitations._get_requestor_email")
    def test_send_email_success(self, mock_get_requestor_email, mock_send_email):
        """Test that the email is sent successfully when there are no errors."""
        # Mock data
        requestor = MagicMock()
        invitation = MagicMock(spec=PortfolioInvitation)
        invitation.email = "user@example.com"
        invitation.portfolio.organization_name = "Test Portfolio"

        mock_get_requestor_email.return_value = "requestor@example.com"

        # Call function
        result = send_portfolio_invitation_remove_email(requestor, invitation)

        # Assertions
        mock_get_requestor_email.assert_called_once_with(requestor, portfolio=invitation.portfolio)
        mock_send_email.assert_called_once_with(
            "emails/portfolio_removal.txt",
            "emails/portfolio_removal_subject.txt",
            to_addresses=["user@example.com"],
            context={
                "requested_user": None,
                "portfolio": invitation.portfolio,
                "requestor_email": "requestor@example.com",
            },
        )
        self.assertTrue(result)

    @patch("registrar.utility.email_invitations.send_templated_email", side_effect=EmailSendingError("Email failed"))
    @patch("registrar.utility.email_invitations._get_requestor_email")
    @patch("registrar.utility.email_invitations.logger")
    def test_send_email_failure(self, mock_logger, mock_get_requestor_email, mock_send_email):
        """Test that the function returns False and logs an error when email sending fails."""
        # Mock data
        requestor = MagicMock()
        invitation = MagicMock(spec=PortfolioInvitation)
        invitation.email = "user@example.com"
        invitation.portfolio.organization_name = "Test Portfolio"

        mock_get_requestor_email.return_value = "requestor@example.com"

        # Call function
        result = send_portfolio_invitation_remove_email(requestor, invitation)

        # Assertions
        mock_logger.error.assert_called_once_with(
            "Failed to send portfolio invitation removal email:\n"
            f"  Subject template: portfolio_removal_subject.txt\n"
            f"  To: {invitation.email}\n"
            f"  Portfolio: {invitation.portfolio.organization_name}\n"
            f"  Error: Email failed",
            exc_info=True,
        )
        self.assertFalse(result)

    @patch("registrar.utility.email_invitations._get_requestor_email", side_effect=Exception("Unexpected error"))
    @patch("registrar.utility.email_invitations.logger")
    def test_requestor_email_retrieval_failure(self, mock_logger, mock_get_requestor_email):
        """Test that an exception in retrieving requestor email is logged."""
        # Mock data
        requestor = MagicMock()
        invitation = MagicMock(spec=PortfolioInvitation)

        # Call function
        with self.assertRaises(Exception):
            send_portfolio_invitation_remove_email(requestor, invitation)

        # Assertions
        mock_logger.warning.assert_not_called()  # Function should fail before logging email failure


class SendDomainManagerRemovalEmailsToManagersTests(unittest.TestCase):
    """Unit tests for send_domain_manager_removal_emails_to_domain_managers function."""

    def setUp(self):
        """Set up test data."""
        self.email = "removed.admin@example.com"
        self.requestor_email = "requestor@example.com"
        self.domain = MagicMock(spec=Domain)
        self.domain.name = "Test Domain"

        # Mock domain manager users
        self.manager_user1 = MagicMock(spec=User)
        self.manager_user1.email = "manager1@example.com"

        self.manager_user2 = MagicMock(spec=User)
        self.manager_user2.email = "manager2@example.com"

        self.domain_manager1 = MagicMock(spec=UserDomainRole)
        self.domain_manager1.user = self.manager_user1

        self.domain_manager2 = MagicMock(spec=UserDomainRole)
        self.domain_manager2.user = self.manager_user2

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.send_templated_email")
    @patch("registrar.utility.email_invitations.UserDomainRole.objects.filter")
    def test_send_email_success(self, mock_filter, mock_send_templated_email):
        """Test successful sending of domain manager removal emails."""
        mock_filter.return_value.exclude.return_value = [self.domain_manager1]
        mock_send_templated_email.return_value = None  # No exception means success

        result = send_domain_manager_removal_emails_to_domain_managers(
            removed_by_user=self.manager_user1,
            manager_removed=self.manager_user2,
            manager_removed_email=self.manager_user2.email,
            domain=self.domain,
        )

        mock_filter.assert_called_once_with(domain=self.domain)
        mock_send_templated_email.assert_any_call(
            "emails/domain_manager_deleted_notification.txt",
            "emails/domain_manager_deleted_notification_subject.txt",
            to_addresses=[self.manager_user1.email],
            context={
                "domain": self.domain,
                "removed_by": self.manager_user1,
                "manager_removed_email": self.manager_user2.email,
                "date": date.today(),
            },
        )
        self.assertTrue(result)

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.send_templated_email")
    @patch("registrar.utility.email_invitations.UserDomainRole.objects.filter")
    def test_send_email_success_when_no_user(self, mock_filter, mock_send_templated_email):
        """Test successful sending of domain manager removal emails."""
        mock_filter.return_value = [self.domain_manager1, self.domain_manager2]
        mock_send_templated_email.return_value = None  # No exception means success

        result = send_domain_manager_removal_emails_to_domain_managers(
            removed_by_user=self.manager_user1,
            manager_removed=None,
            manager_removed_email=self.manager_user2.email,
            domain=self.domain,
        )

        mock_filter.assert_called_once_with(domain=self.domain)
        mock_send_templated_email.assert_any_call(
            "emails/domain_manager_deleted_notification.txt",
            "emails/domain_manager_deleted_notification_subject.txt",
            to_addresses=[self.manager_user1.email],
            context={
                "domain": self.domain,
                "removed_by": self.manager_user1,
                "manager_removed_email": self.manager_user2.email,
                "date": date.today(),
            },
        )
        mock_send_templated_email.assert_any_call(
            "emails/domain_manager_deleted_notification.txt",
            "emails/domain_manager_deleted_notification_subject.txt",
            to_addresses=[self.manager_user2.email],
            context={
                "domain": self.domain,
                "removed_by": self.manager_user1,
                "manager_removed_email": self.manager_user2.email,
                "date": date.today(),
            },
        )
        self.assertTrue(result)

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.send_templated_email", side_effect=EmailSendingError)
    @patch("registrar.utility.email_invitations.UserDomainRole.objects.filter")
    def test_send_email_failure(self, mock_filter, mock_send_templated_email):
        """Test handling of failure in sending admin removal emails."""
        mock_filter.return_value.exclude.return_value = [self.domain_manager1, self.domain_manager2]

        result = send_domain_manager_removal_emails_to_domain_managers(
            removed_by_user=self.manager_user1,
            manager_removed=self.manager_user2,
            manager_removed_email=self.manager_user2.email,
            domain=self.domain,
        )

        self.assertFalse(result)
        mock_filter.assert_called_once_with(domain=self.domain)
        mock_send_templated_email.assert_any_call(
            "emails/domain_manager_deleted_notification.txt",
            "emails/domain_manager_deleted_notification_subject.txt",
            to_addresses=[self.manager_user1.email],
            context={
                "domain": self.domain,
                "removed_by": self.manager_user1,
                "manager_removed_email": self.manager_user2.email,
                "date": date.today(),
            },
        )
        mock_send_templated_email.assert_any_call(
            "emails/domain_manager_deleted_notification.txt",
            "emails/domain_manager_deleted_notification_subject.txt",
            to_addresses=[self.manager_user2.email],
            context={
                "domain": self.domain,
                "removed_by": self.manager_user1,
                "manager_removed_email": self.manager_user2.email,
                "date": date.today(),
            },
        )

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.UserDomainRole.objects.filter")
    def test_no_managers_to_notify(self, mock_filter):
        """Test case where there are no domain managers to notify."""
        mock_filter.return_value.exclude.return_value = []  # No managers

        result = send_domain_manager_removal_emails_to_domain_managers(
            removed_by_user=self.manager_user1,
            manager_removed=self.manager_user2,
            manager_removed_email=self.manager_user2.email,
            domain=self.domain,
        )

        self.assertTrue(result)  # No emails sent, but also no failures
        mock_filter.assert_called_once_with(domain=self.domain)


class TestSendPortfolioOrganizationUpdateEmail(unittest.TestCase):
    """Unit tests for send_portfolio_update_emails_to_portfolio_admins function."""

    def setUp(self):
        """Set up test data."""
        self.email = "removed.admin@example.com"
        self.requestor_email = "requestor@example.com"
        self.portfolio = MagicMock(spec=Portfolio, name="Portfolio")
        self.portfolio.organization_name = "Test Organization"

        # Mock portfolio admin users
        self.admin_user1 = MagicMock(spec=User)
        self.admin_user1.email = "admin1@example.com"

        self.admin_user2 = MagicMock(spec=User)
        self.admin_user2.email = "admin2@example.com"

        self.portfolio_admin1 = MagicMock(spec=UserPortfolioPermission)
        self.portfolio_admin1.user = self.admin_user1
        self.portfolio_admin1.roles = [UserPortfolioRoleChoices.ORGANIZATION_ADMIN]

        self.portfolio_admin2 = MagicMock(spec=UserPortfolioPermission)
        self.portfolio_admin2.user = self.admin_user2
        self.portfolio_admin2.roles = [UserPortfolioRoleChoices.ORGANIZATION_ADMIN]

    @patch("registrar.utility.email_invitations.send_templated_email")
    @patch("registrar.utility.email_invitations.UserPortfolioPermission.objects.filter")
    def test_send_portfolio_update_emails_to_portfolio_admins(self, mock_filter, mock_send_templated_email):
        """Test send_portfolio_update_emails_to_portfolio_admins sends templated email."""
        # Mock data
        editor = self.admin_user1
        updated_page = "Organization"

        mock_filter.return_value = [self.portfolio_admin1, self.portfolio_admin2]
        mock_send_templated_email.return_value = None  # No exception means success

        # Call function
        result = send_portfolio_update_emails_to_portfolio_admins(editor, self.portfolio, updated_page)

        mock_filter.assert_called_once_with(
            portfolio=self.portfolio, roles__contains=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )
        mock_send_templated_email.assert_any_call(
            "emails/portfolio_org_update_notification.txt",
            "emails/portfolio_org_update_notification_subject.txt",
            to_addresses=self.admin_user1.email,
            context=ANY,
        )
        mock_send_templated_email.assert_any_call(
            "emails/portfolio_org_update_notification.txt",
            "emails/portfolio_org_update_notification_subject.txt",
            to_addresses=self.admin_user2.email,
            context=ANY,
        )
        self.assertTrue(result)


class TestDomainInvitationCleanupSignal(TestCase):
    """Integration tests for the signal that cleans up retrieved invitations when UserDomainRole is deleted."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(email="test@example.com", username="testuser")
        self.domain = Domain.objects.create(name="test.gov")

    def test_retrieved_invitation_cleaned_up_when_role_deleted(self):
        """Test that retrieved invitations are deleted when UserDomainRole is deleted."""
        # Create and retrieve an invitation
        invitation = DomainInvitation.objects.create(
            email=self.user.email, domain=self.domain, status=DomainInvitation.DomainInvitationStatus.INVITED
        )
        invitation.retrieve()
        invitation.save()

        # Verify setup
        self.assertEqual(invitation.status, DomainInvitation.DomainInvitationStatus.RETRIEVED)
        role = UserDomainRole.objects.get(user=self.user, domain=self.domain)
        self.assertTrue(DomainInvitation.objects.filter(id=invitation.id).exists())

        # Delete the role (this should trigger the new signal)
        role.delete()

        # Verify the invitation was cleaned up
        self.assertFalse(DomainInvitation.objects.filter(id=invitation.id).exists())

    def test_bug_fix_can_re_add_user_after_removal(self):
        """Test the complete flow that reproduces and verifies the fix for ticket #3678."""
        invitation = DomainInvitation.objects.create(
            email=self.user.email, domain=self.domain, status=DomainInvitation.DomainInvitationStatus.INVITED
        )
        invitation.retrieve()
        invitation.save()

        # Remove the user (simulating admin removing domain manager)
        role = UserDomainRole.objects.get(user=self.user, domain=self.domain)
        role.delete()

        self.assertFalse(DomainInvitation.objects.filter(id=invitation.id).exists())

        # Create another invitation
        invitation = DomainInvitation.objects.create(
            email=self.user.email, domain=self.domain, status=DomainInvitation.DomainInvitationStatus.INVITED
        )
        invitation.retrieve()
        invitation.save()

        # Verify setup
        self.assertEqual(invitation.status, DomainInvitation.DomainInvitationStatus.RETRIEVED)
        role = UserDomainRole.objects.get(user=self.user, domain=self.domain)
        self.assertTrue(DomainInvitation.objects.filter(id=invitation.id).exists())

        self.assertTrue(UserDomainRole.objects.filter(user=self.user, domain=self.domain).exists())


class TestSendDomainManagerOnHoldEmail(unittest.TestCase):
    """Unit tests for send_domain_manager_on_hold_email_to_domain_managers function."""

    def setUp(self):
        """Set up test data."""
        self.domain = MagicMock(spec=Domain)
        self.domain.name = "Test On Hold Domain"

        self.dm1 = MagicMock(spec=UserDomainRole)
        self.dm1.user = MagicMock(spec=User)
        self.dm1.user.email = "domain_manager_1@example.com"

        self.dm2 = MagicMock(spec=UserDomainRole)
        self.dm2.user = MagicMock(spec=User)
        self.dm2.user.email = "domain_manager_2@example.com"

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.send_templated_email")
    @patch("registrar.utility.email_invitations.UserDomainRole.objects.filter")
    def test_send_email_success(self, mock_filter, mock_send_templated_email):
        """Test successful sending of domain manager removal emails."""

        mock_filter.return_value = [self.dm1, self.dm2]
        mock_send_templated_email.return_value = None  # No exception means success

        result = send_domain_manager_on_hold_email_to_domain_managers(
            domain=self.domain,
        )

        mock_filter.assert_called_once_with(domain=self.domain)
        mock_send_templated_email.assert_any_call(
            "emails/domain_on_hold_notification.txt",
            "emails/domain_on_hold_notification_subject.txt",
            to_addresses=[self.dm1.user.email],
            bcc_address="",
            context={
                "domain_manager": self.dm1.user,
                "domain": self.domain,
                "date": date.today(),
            },
        )

        mock_send_templated_email.assert_any_call(
            "emails/domain_on_hold_notification.txt",
            "emails/domain_on_hold_notification_subject.txt",
            to_addresses=[self.dm2.user.email],
            bcc_address="",
            context={
                "domain_manager": self.dm2.user,
                "domain": self.domain,
                "date": date.today(),
            },
        )

        self.assertTrue(result)

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.send_templated_email", side_effect=EmailSendingError)
    @patch("registrar.utility.email_invitations.UserDomainRole.objects.filter")
    def test_send_email_failure(self, mock_filter, mock_send_templated_email):
        mock_filter.return_value = [self.dm1, self.dm2]

        result = send_domain_manager_on_hold_email_to_domain_managers(
            domain=self.domain,
        )

        self.assertFalse(result)
        mock_filter.assert_called_once_with(domain=self.domain)
        mock_send_templated_email.assert_any_call(
            "emails/domain_on_hold_notification.txt",
            "emails/domain_on_hold_notification_subject.txt",
            to_addresses=[self.dm1.user.email],
            bcc_address="",
            context={
                "domain_manager": self.dm1.user,
                "domain": self.domain,
                "date": date.today(),
            },
        )
        mock_send_templated_email.assert_any_call(
            "emails/domain_on_hold_notification.txt",
            "emails/domain_on_hold_notification_subject.txt",
            to_addresses=[self.dm2.user.email],
            bcc_address="",
            context={
                "domain_manager": self.dm2.user,
                "domain": self.domain,
                "date": date.today(),
            },
        )


class TestDomainRenewalNotificationEmail(unittest.TestCase):
    """
    Unit tests for send_domain_renewal_notification_emails function
    """

    def setUp(self):
        # Creates mock users with email addresses
        self.user_1 = MagicMock()
        self.user_1.email = "user1@example.gov"
        self.user_2 = MagicMock(spec=User)
        self.user_2.email = "user2@example.gov"

        # Create mock domain
        self.domain = MagicMock(spec=Domain)
        self.domain.name = "domainrenewal.gov"
        self.domain.expiration_date = date.today()

        # Create mock portfolio
        self.portfolio = MagicMock()

        # Create mock domain information
        self.domain_info = MagicMock()
        self.domain_info.portfolio = self.portfolio

    def _setup_mocks(self, mock_domain_information_filter, mock_domain_role_filter, has_portfolio=True):
        """Helper method to configure common mocks for tests

        Args:
            mock_domain_information_filter: Mock for DomainInformation.objects.filter
            mock_domain_role_filter: Mock for UserDomainRole.objects.filter
            has_portfolio: Whether the domain should have an associated portfolio
        """
        # Mock the domain manager query chain
        mock_values_list_qs = MagicMock()
        mock_values_list_qs.distinct.return_value = [self.user_1.email]
        mock_domain_role_filter.return_value.values_list.return_value = mock_values_list_qs

        # Mock the domain information query
        mock_queryset_domain_info = MagicMock()
        mock_queryset_domain_info.first.return_value = self.domain_info
        mock_domain_information_filter.return_value = mock_queryset_domain_info

        if has_portfolio:
            # Mock the portfolio admin users query chain
            mock_admins_qs = MagicMock()
            mock_admins_qs.distinct.return_value = [self.user_2.email]
            mock_portfolio_user_qs = MagicMock()
            mock_portfolio_user_qs.values_list.return_value = mock_admins_qs
            self.portfolio.portfolio_admin_users = mock_portfolio_user_qs
            self.domain_info.portfolio = self.portfolio
        else:
            # Domain has no assocated portfolio
            self.domain_info.portfolio = None

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.send_templated_email")
    @patch("registrar.utility.email_invitations.UserDomainRole.objects.filter")
    @patch("registrar.utility.email_invitations.DomainInformation.objects.filter")
    def test_send_email_success_with_org_admin_and_portfolio(
        self, mock_domain_information_filter, mock_domain_role_filter, mock_send_templated_email
    ):
        """Test successful sending of domain renewal emails with a portfolio and an org admin"""

        self._setup_mocks(mock_domain_information_filter, mock_domain_role_filter)
        mock_send_templated_email.return_value = None  # No exception means success

        result = send_domain_renewal_notification_emails(
            domain=self.domain,
        )

        mock_domain_role_filter.assert_called_once_with(domain=self.domain)
        mock_domain_information_filter.assert_called_once_with(domain=self.domain)
        mock_send_templated_email.assert_any_call(
            template_name="emails/domain_renewal_success.txt",
            subject_template_name="emails/domain_renewal_success_subject.txt",
            to_addresses=[self.user_1.email],
            cc_addresses=[self.user_2.email],
            context={"domain": self.domain, "expiration_date": self.domain.expiration_date},
        )
        self.assertTrue(result)

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.send_templated_email")
    @patch("registrar.utility.email_invitations.UserDomainRole.objects.filter")
    @patch("registrar.utility.email_invitations.DomainInformation.objects.filter")
    def test_send_email_success_with_portfolio_with_no_org_admin(
        self, mock_domain_information_filter, mock_domain_role_filter, mock_send_templated_email
    ):
        """Test successful sending of domain renewal emails without org admins and a portfolio."""
        self._setup_mocks(mock_domain_information_filter, mock_domain_role_filter, has_portfolio=False)
        mock_send_templated_email.return_value = None  # No exception means success

        self.domain_info.portfolio = self.portfolio  # Attaches a portfolio with no org admin

        result = send_domain_renewal_notification_emails(
            domain=self.domain,
        )

        mock_domain_role_filter.assert_called_once_with(domain=self.domain)
        mock_domain_information_filter.assert_called_once_with(domain=self.domain)
        mock_send_templated_email.assert_any_call(
            template_name="emails/domain_renewal_success.txt",
            subject_template_name="emails/domain_renewal_success_subject.txt",
            to_addresses=[self.user_1.email],
            cc_addresses=[],
            context={"domain": self.domain, "expiration_date": self.domain.expiration_date},
        )
        self.assertTrue(result)

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.send_templated_email", side_effect=EmailSendingError)
    @patch("registrar.utility.email_invitations.UserDomainRole.objects.filter")
    @patch("registrar.utility.email_invitations.DomainInformation.objects.filter")
    def test_send_email_failure(
        self, mock_domain_information_filter, mock_domain_role_filter, mock_send_templated_email
    ):
        """Test failure sending of domain renewal emails."""
        self._setup_mocks(mock_domain_information_filter, mock_domain_role_filter)
        mock_send_templated_email.return_value = None  # No exception means success

        result = send_domain_renewal_notification_emails(
            domain=self.domain,
        )

        mock_domain_role_filter.assert_called_once_with(domain=self.domain)
        mock_domain_information_filter.assert_called_once_with(domain=self.domain)
        mock_send_templated_email.assert_any_call(
            template_name="emails/domain_renewal_success.txt",
            subject_template_name="emails/domain_renewal_success_subject.txt",
            to_addresses=[self.user_1.email],
            cc_addresses=[self.user_2.email],
            context={"domain": self.domain, "expiration_date": self.domain.expiration_date},
        )
        self.assertFalse(result)

    @less_console_noise_decorator
    @patch("registrar.utility.email_invitations.send_templated_email")
    @patch("registrar.utility.email_invitations.UserDomainRole.objects.filter")
    @patch("registrar.utility.email_invitations.DomainInformation.objects.filter")
    def test_send_email_success_with_no_org_admins_and_no_portfolio(
        self, mock_domain_information_filter, mock_domain_role_filter, mock_send_templated_email
    ):
        """Test successful sending of domain renewal emails without portfolio and any org admins."""
        self._setup_mocks(mock_domain_information_filter, mock_domain_role_filter, has_portfolio=False)
        mock_send_templated_email.return_value = None  # No exception means success

        result = send_domain_renewal_notification_emails(
            domain=self.domain,
        )

        mock_domain_role_filter.assert_called_once_with(domain=self.domain)
        mock_domain_information_filter.assert_called_once_with(domain=self.domain)
        mock_send_templated_email.assert_any_call(
            template_name="emails/domain_renewal_success.txt",
            subject_template_name="emails/domain_renewal_success_subject.txt",
            to_addresses=[self.user_1.email],
            cc_addresses=[],
            context={"domain": self.domain, "expiration_date": self.domain.expiration_date},
        )
        self.assertTrue(result)
