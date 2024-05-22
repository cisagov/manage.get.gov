from datetime import date
from django.test import Client, TestCase, override_settings
from django.contrib.auth import get_user_model

from api.tests.common import less_console_noise_decorator
from registrar.models.contact import Contact
from registrar.models.domain import Domain
from registrar.models.draft_domain import DraftDomain
from registrar.models.user import User
from registrar.models.user_domain_role import UserDomainRole
from registrar.views.domain import DomainNameserversView

from .common import MockEppLib, less_console_noise  # type: ignore
from unittest.mock import patch
from django.urls import reverse

from registrar.models import (
    DomainRequest,
    DomainInformation,
)
import logging

logger = logging.getLogger(__name__)


class TestViews(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health_check_endpoint(self):
        response = self.client.get("/health")
        self.assertContains(response, "OK", status_code=200)

    def test_home_page(self):
        """Home page should NOT be available without a login."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)

    def test_domain_request_form_not_logged_in(self):
        """Domain request form not accessible without a logged-in user."""
        response = self.client.get("/request/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login?next=/request/", response.headers["Location"])


class TestWithUser(MockEppLib):
    def setUp(self):
        super().setUp()
        username = "test_user"
        first_name = "First"
        last_name = "Last"
        email = "info@example.com"
        self.user = get_user_model().objects.create(
            username=username, first_name=first_name, last_name=last_name, email=email
        )

    def tearDown(self):
        # delete any domain requests too
        super().tearDown()
        DomainRequest.objects.all().delete()
        DomainInformation.objects.all().delete()
        self.user.delete()


class TestEnvironmentVariablesEffects(TestCase):
    def setUp(self):
        self.client = Client()
        username = "test_user"
        first_name = "First"
        last_name = "Last"
        email = "info@example.com"
        self.user = get_user_model().objects.create(
            username=username, first_name=first_name, last_name=last_name, email=email
        )
        self.client.force_login(self.user)

    def tearDown(self):
        super().tearDown()
        Domain.objects.all().delete()
        self.user.delete()

    @override_settings(IS_PRODUCTION=True)
    def test_production_environment(self):
        """No banner on prod."""
        home_page = self.client.get("/")
        self.assertNotContains(home_page, "You are on a test site.")

    @override_settings(IS_PRODUCTION=False)
    def test_non_production_environment(self):
        """Banner on non-prod."""
        home_page = self.client.get("/")
        self.assertContains(home_page, "You are on a test site.")

    def side_effect_raise_value_error(self):
        """Side effect that raises a 500 error"""
        raise ValueError("Some error")

    @less_console_noise_decorator
    @override_settings(IS_PRODUCTION=False)
    def test_non_production_environment_raises_500_and_shows_banner(self):
        """Tests if the non-prod banner is still shown on a 500"""
        fake_domain, _ = Domain.objects.get_or_create(name="igorville.gov")

        # Add a role
        fake_role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=fake_domain, role=UserDomainRole.Roles.MANAGER
        )

        with patch.object(DomainNameserversView, "get_initial", side_effect=self.side_effect_raise_value_error):
            with self.assertRaises(ValueError):
                contact_page_500 = self.client.get(
                    reverse("domain-dns-nameservers", kwargs={"pk": fake_domain.id}),
                )

                # Check that a 500 response is returned
                self.assertEqual(contact_page_500.status_code, 500)

                self.assertContains(contact_page_500, "You are on a test site.")

    @less_console_noise_decorator
    @override_settings(IS_PRODUCTION=True)
    def test_production_environment_raises_500_and_doesnt_show_banner(self):
        """Test if the non-prod banner is not shown on production when a 500 is raised"""

        fake_domain, _ = Domain.objects.get_or_create(name="igorville.gov")

        # Add a role
        fake_role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=fake_domain, role=UserDomainRole.Roles.MANAGER
        )

        with patch.object(DomainNameserversView, "get_initial", side_effect=self.side_effect_raise_value_error):
            with self.assertRaises(ValueError):
                contact_page_500 = self.client.get(
                    reverse("domain-dns-nameservers", kwargs={"pk": fake_domain.id}),
                )

                # Check that a 500 response is returned
                self.assertEqual(contact_page_500.status_code, 500)

                self.assertNotContains(contact_page_500, "You are on a test site.")


class HomeTests(TestWithUser):
    """A series of tests that target the two tables on home.html"""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def tearDown(self):
        super().tearDown()
        Contact.objects.all().delete()

    def test_empty_domain_table(self):
        response = self.client.get("/")
        self.assertContains(response, "You don't have any registered domains.")
        self.assertContains(response, "Why don't I see my domain when I sign in to the registrar?")

    def test_state_help_text(self):
        """Tests if each domain state has help text"""

        # Get the expected text content of each state
        deleted_text = "This domain has been removed and " "is no longer registered to your organization."
        dns_needed_text = "Before this domain can be used, "
        ready_text = "This domain has name servers and is ready for use."
        on_hold_text = (
            "This domain is administratively paused, "
        )
        deleted_text = "This domain has been removed and " "is no longer registered to your organization."
        # Generate a mapping of domain names, the state, and expected messages for the subtest
        test_cases = [
            ("deleted.gov", Domain.State.DELETED, deleted_text),
            ("dnsneeded.gov", Domain.State.DNS_NEEDED, dns_needed_text),
            ("unknown.gov", Domain.State.UNKNOWN, dns_needed_text),
            ("onhold.gov", Domain.State.ON_HOLD, on_hold_text),
            ("ready.gov", Domain.State.READY, ready_text),
        ]
        for domain_name, state, expected_message in test_cases:
            with self.subTest(domain_name=domain_name, state=state, expected_message=expected_message):
                # Create a domain and a UserRole with the given params
                test_domain, _ = Domain.objects.get_or_create(name=domain_name, state=state)
                test_domain.expiration_date = date.today()
                test_domain.save()

                user_role, _ = UserDomainRole.objects.get_or_create(
                    user=self.user, domain=test_domain, role=UserDomainRole.Roles.MANAGER
                )

                # Grab the response
                response = self.client.get("/get-domains-json/")

                # Make sure the user can actually see the domain.
                # We expect two instances because of SR content.
                self.assertContains(response, domain_name, count=1)

                # Check that we have the right text content.
                self.assertContains(response, expected_message, count=1)

                # Delete the role and domain to ensure we're testing in isolation
                user_role.delete()
                test_domain.delete()

    def test_state_help_text_expired(self):
        """Tests if each domain state has help text when expired"""
        expired_text = "This domain has expired, but it is still online. "
        test_domain, _ = Domain.objects.get_or_create(name="expired.gov", state=Domain.State.READY)
        test_domain.expiration_date = date(2011, 10, 10)
        test_domain.save()

        UserDomainRole.objects.get_or_create(user=self.user, domain=test_domain, role=UserDomainRole.Roles.MANAGER)

        # Grab the response
        response = self.client.get("/get-domains-json/")

        # Make sure the user can actually see the domain.
        # We expect two instances because of SR content.
        self.assertContains(response, "expired.gov", count=1)

        # Check that we have the right text content.
        self.assertContains(response, expired_text, count=1)

    def test_state_help_text_no_expiration_date(self):
        """Tests if each domain state has help text when expiration date is None"""

        # == Test a expiration of None for state ready. This should be expired. == #
        expired_text = "This domain has expired, but it is still online. "
        test_domain, _ = Domain.objects.get_or_create(name="imexpired.gov", state=Domain.State.READY)
        test_domain.expiration_date = None
        test_domain.save()

        UserDomainRole.objects.get_or_create(user=self.user, domain=test_domain, role=UserDomainRole.Roles.MANAGER)

        # Grab the response
        response = self.client.get("/get-domains-json/")

        self.assertContains(response, "imexpired.gov", count=1)

        # Make sure the expiration date is None
        self.assertEqual(test_domain.expiration_date, None)

        # Check that we have the right text content.
        self.assertContains(response, expired_text, count=1)

        # == Test a expiration of None for state unknown. This should not display expired text. == #
        unknown_text = "Before this domain can be used, "
        test_domain_2, _ = Domain.objects.get_or_create(name="notexpired.gov", state=Domain.State.UNKNOWN)
        test_domain_2.expiration_date = None
        test_domain_2.save()

        UserDomainRole.objects.get_or_create(user=self.user, domain=test_domain_2, role=UserDomainRole.Roles.MANAGER)

        # Grab the response
        response = self.client.get("/get-domains-json/")

        self.assertContains(response, "notexpired.gov", count=1)

        # Make sure the expiration date is None
        self.assertEqual(test_domain_2.expiration_date, None)

        # Check that we have the right text content.
        self.assertContains(response, unknown_text, count=1)

    def test_home_deletes_withdrawn_domain_request(self):
        """Tests if the user can delete a DomainRequest in the 'withdrawn' status"""

        site = DraftDomain.objects.create(name="igorville.gov")
        domain_request = DomainRequest.objects.create(
            creator=self.user, requested_domain=site, status=DomainRequest.DomainRequestStatus.WITHDRAWN
        )

        # Trigger the delete logic
        response = self.client.post(reverse("domain-request-delete", kwargs={"pk": domain_request.pk}), follow=True)

        self.assertNotContains(response, "igorville.gov")

        # clean up
        domain_request.delete()

    def test_home_deletes_started_domain_request(self):
        """Tests if the user can delete a DomainRequest in the 'started' status"""

        site = DraftDomain.objects.create(name="igorville.gov")
        domain_request = DomainRequest.objects.create(
            creator=self.user, requested_domain=site, status=DomainRequest.DomainRequestStatus.STARTED
        )

        # Trigger the delete logic
        response = self.client.post(reverse("domain-request-delete", kwargs={"pk": domain_request.pk}), follow=True)

        self.assertNotContains(response, "igorville.gov")

        # clean up
        domain_request.delete()

    def test_home_doesnt_delete_other_domain_requests(self):
        """Tests to ensure the user can't delete domain requests not in the status of STARTED or WITHDRAWN"""

        # Given that we are including a subset of items that can be deleted while excluding the rest,
        # subTest is appropriate here as otherwise we would need many duplicate tests for the same reason.
        with less_console_noise():
            draft_domain = DraftDomain.objects.create(name="igorville.gov")
            for status in DomainRequest.DomainRequestStatus:
                if status not in [
                    DomainRequest.DomainRequestStatus.STARTED,
                    DomainRequest.DomainRequestStatus.WITHDRAWN,
                ]:
                    with self.subTest(status=status):
                        domain_request = DomainRequest.objects.create(
                            creator=self.user, requested_domain=draft_domain, status=status
                        )

                        # Trigger the delete logic
                        response = self.client.post(
                            reverse("domain-request-delete", kwargs={"pk": domain_request.pk}), follow=True
                        )

                        # Check for a 403 error - the end user should not be allowed to do this
                        self.assertEqual(response.status_code, 403)

                        desired_domain_request = DomainRequest.objects.filter(requested_domain=draft_domain)

                        # Make sure the DomainRequest wasn't deleted
                        self.assertEqual(desired_domain_request.count(), 1)

                        # clean up
                        domain_request.delete()

    def test_home_deletes_domain_request_and_orphans(self):
        """Tests if delete for DomainRequest deletes orphaned Contact objects"""

        # Create the site and contacts to delete (orphaned)
        contact = Contact.objects.create(
            first_name="Henry",
            last_name="Mcfakerson",
        )
        contact_shared = Contact.objects.create(
            first_name="Relative",
            last_name="Aether",
        )

        # Create two non-orphaned contacts
        contact_2 = Contact.objects.create(
            first_name="Saturn",
            last_name="Mars",
        )

        # Attach a user object to a contact (should not be deleted)
        contact_user, _ = Contact.objects.get_or_create(user=self.user)

        site = DraftDomain.objects.create(name="igorville.gov")
        domain_request = DomainRequest.objects.create(
            creator=self.user,
            requested_domain=site,
            status=DomainRequest.DomainRequestStatus.WITHDRAWN,
            authorizing_official=contact,
            submitter=contact_user,
        )
        domain_request.other_contacts.set([contact_2])

        # Create a second domain request to attach contacts to
        site_2 = DraftDomain.objects.create(name="teaville.gov")
        domain_request_2 = DomainRequest.objects.create(
            creator=self.user,
            requested_domain=site_2,
            status=DomainRequest.DomainRequestStatus.STARTED,
            authorizing_official=contact_2,
            submitter=contact_shared,
        )
        domain_request_2.other_contacts.set([contact_shared])

        # Ensure that igorville.gov exists on the page
        home_page = self.client.get("/")
        self.assertContains(home_page, "igorville.gov")

        # Trigger the delete logic
        response = self.client.post(reverse("domain-request-delete", kwargs={"pk": domain_request.pk}), follow=True)

        # igorville is now deleted
        self.assertNotContains(response, "igorville.gov")

        # Check if the orphaned contact was deleted
        orphan = Contact.objects.filter(id=contact.id)
        self.assertFalse(orphan.exists())

        # All non-orphan contacts should still exist and are unaltered
        try:
            current_user = Contact.objects.filter(id=contact_user.id).get()
        except Contact.DoesNotExist:
            self.fail("contact_user (a non-orphaned contact) was deleted")

        self.assertEqual(current_user, contact_user)
        try:
            edge_case = Contact.objects.filter(id=contact_2.id).get()
        except Contact.DoesNotExist:
            self.fail("contact_2 (a non-orphaned contact) was deleted")

        self.assertEqual(edge_case, contact_2)

    def test_home_deletes_domain_request_and_shared_orphans(self):
        """Test the edge case for an object that will become orphaned after a delete
        (but is not an orphan at the time of deletion)"""

        # Create the site and contacts to delete (orphaned)
        contact = Contact.objects.create(
            first_name="Henry",
            last_name="Mcfakerson",
        )
        contact_shared = Contact.objects.create(
            first_name="Relative",
            last_name="Aether",
        )

        # Create two non-orphaned contacts
        contact_2 = Contact.objects.create(
            first_name="Saturn",
            last_name="Mars",
        )

        # Attach a user object to a contact (should not be deleted)
        contact_user, _ = Contact.objects.get_or_create(user=self.user)

        site = DraftDomain.objects.create(name="igorville.gov")
        domain_request = DomainRequest.objects.create(
            creator=self.user,
            requested_domain=site,
            status=DomainRequest.DomainRequestStatus.WITHDRAWN,
            authorizing_official=contact,
            submitter=contact_user,
        )
        domain_request.other_contacts.set([contact_2])

        # Create a second domain request to attach contacts to
        site_2 = DraftDomain.objects.create(name="teaville.gov")
        domain_request_2 = DomainRequest.objects.create(
            creator=self.user,
            requested_domain=site_2,
            status=DomainRequest.DomainRequestStatus.STARTED,
            authorizing_official=contact_2,
            submitter=contact_shared,
        )
        domain_request_2.other_contacts.set([contact_shared])

        home_page = self.client.get("/")
        self.assertContains(home_page, "teaville.gov")

        # Trigger the delete logic
        response = self.client.post(reverse("domain-request-delete", kwargs={"pk": domain_request_2.pk}), follow=True)

        self.assertNotContains(response, "teaville.gov")

        # Check if the orphaned contact was deleted
        orphan = Contact.objects.filter(id=contact_shared.id)
        self.assertFalse(orphan.exists())

    def test_domain_request_form_view(self):
        response = self.client.get("/request/", follow=True)
        self.assertContains(
            response,
            "You’re about to start your .gov domain request.",
        )

    def test_domain_request_form_with_ineligible_user(self):
        """Domain request form not accessible for an ineligible user.
        This test should be solid enough since all domain request wizard
        views share the same permissions class"""
        self.user.status = User.RESTRICTED
        self.user.save()

        with less_console_noise():
            response = self.client.get("/request/", follow=True)
            self.assertEqual(response.status_code, 403)
