"""Regression tests for domain notification recipients using real role queries."""

from datetime import date
from unittest.mock import MagicMock, PropertyMock, patch

from django.test import TestCase

from registrar.models import Domain, UserDomainRole
from registrar.models.user import User
from registrar.utility.email_invitations import (
    send_domain_manager_on_hold_email_to_domain_managers,
    send_domain_renewal_notification_emails,
)


class TestDomainNotificationRecipients(TestCase):
    """Pending invitations must not introduce null email recipients."""

    def setUp(self):
        self.domain = Domain.objects.create(name="notification-example.gov")
        self.manager = User.objects.create_user(username="notified-manager", email="manager@example.org")
        UserDomainRole.objects.create(domain=self.domain, user=self.manager, role=UserDomainRole.Roles.MANAGER)
        expiration = patch.object(Domain, "expiration_date", new_callable=PropertyMock, return_value=date(2027, 9, 10))
        expiration.start()
        self.addCleanup(expiration.stop)

    def add_invitation(self):
        return UserDomainRole.objects.create(
            domain=self.domain,
            user=None,
            role=UserDomainRole.Roles.MANAGER,
            status=UserDomainRole.Status.INVITED,
            email="pending@example.org",
        )

    def add_manager_without_email(self):
        user = User.objects.create_user(username="manager-without-email", email="")
        UserDomainRole.objects.create(domain=self.domain, user=user, role=UserDomainRole.Roles.MANAGER)

    def notification_arguments(self, renewal):
        """Exercise the real ORM selection, replacing only message delivery."""
        with patch("registrar.utility.email_invitations.send_templated_email") as send_email:
            if renewal:
                result = send_domain_renewal_notification_emails(self.domain)
            else:
                result = send_domain_manager_on_hold_email_to_domain_managers(self.domain, self.manager)
        self.assertTrue(result)
        send_email.assert_called_once()
        return send_email.call_args.kwargs

    def test_renewal_skips_pending_invitations(self):
        self.add_invitation()
        self.assertEqual(self.notification_arguments(True)["to_addresses"], [self.manager.email])

    def test_on_hold_skips_pending_invitations(self):
        self.add_invitation()
        self.assertEqual(self.notification_arguments(False)["to_addresses"], [self.manager.email])

    def test_renewal_skips_empty_manager_emails(self):
        self.add_manager_without_email()
        self.assertEqual(self.notification_arguments(True)["to_addresses"], [self.manager.email])

    def test_on_hold_skips_empty_manager_emails(self):
        self.add_manager_without_email()
        self.assertEqual(self.notification_arguments(False)["to_addresses"], [self.manager.email])

    def test_renewal_with_only_invitations_has_no_manager_recipients(self):
        self.add_invitation()
        UserDomainRole.objects.filter(domain=self.domain, user=self.manager).delete()
        self.assertEqual(self.notification_arguments(True)["to_addresses"], [])

    def test_on_hold_with_only_invitations_has_no_manager_recipients(self):
        self.add_invitation()
        UserDomainRole.objects.filter(domain=self.domain, user=self.manager).delete()
        self.assertEqual(self.notification_arguments(False)["to_addresses"], [])

    def test_renewal_keeps_existing_manager_recipients(self):
        self.assertEqual(self.notification_arguments(True)["to_addresses"], [self.manager.email])

    def test_on_hold_keeps_existing_manager_recipients(self):
        arguments = self.notification_arguments(False)
        self.assertEqual(arguments["to_addresses"], [self.manager.email])
        self.assertEqual(arguments["context"]["requestor_email"], self.manager.email)

    def test_renewal_keeps_organization_admin_recipients(self):
        domain_info = MagicMock()
        domain_info.portfolio.portfolio_admin_users.values_list.return_value.distinct.return_value = [
            "admin@example.org"
        ]
        with patch("registrar.utility.email_invitations.DomainInformation.objects.filter") as domain_information:
            domain_information.return_value.first.return_value = domain_info
            arguments = self.notification_arguments(True)
        self.assertEqual(arguments["to_addresses"], [self.manager.email])
        self.assertEqual(arguments["cc_addresses"], ["admin@example.org"])
