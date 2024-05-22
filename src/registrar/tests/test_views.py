from datetime import date
from django.test import Client, TestCase, override_settings
from django.contrib.auth import get_user_model
from django_webtest import WebTest  # type: ignore
from django.conf import settings

from api.tests.common import less_console_noise_decorator
from registrar.models.contact import Contact
from registrar.models.domain import Domain
from registrar.models.draft_domain import DraftDomain
from registrar.models.public_contact import PublicContact
from registrar.models.user import User
from registrar.models.user_domain_role import UserDomainRole
from registrar.views.domain import DomainNameserversView

from .common import MockEppLib, less_console_noise  # type: ignore
from unittest.mock import patch
from django.urls import reverse

from registrar.models import (
    DomainRequest,
    DomainInformation,
    Website,
)
from waffle.testutils import override_flag
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
        phone = "8003111234"
        self.user = get_user_model().objects.create(
            username=username, first_name=first_name, last_name=last_name, email=email, phone=phone
        )
        title = "test title"
        self.user.contact.title = title
        self.user.save()

        username_incomplete = "test_user_incomplete"
        first_name_2 = "Incomplete"
        email_2 = "unicorn@igorville.com"
        self.incomplete_user = get_user_model().objects.create(
            username=username_incomplete, first_name=first_name_2, email=email_2
        )

    def tearDown(self):
        # delete any domain requests too
        super().tearDown()
        DomainRequest.objects.all().delete()
        DomainInformation.objects.all().delete()
        self.user.delete()
        self.incomplete_user.delete()


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

    def test_home_lists_domain_requests(self):
        response = self.client.get("/")
        self.assertNotContains(response, "igorville.gov")
        site = DraftDomain.objects.create(name="igorville.gov")
        domain_request = DomainRequest.objects.create(creator=self.user, requested_domain=site)
        response = self.client.get("/")

        # count = 7 because of screenreader content
        self.assertContains(response, "igorville.gov", count=7)

        # clean up
        domain_request.delete()

    def test_state_help_text(self):
        """Tests if each domain state has help text"""

        # Get the expected text content of each state
        deleted_text = "This domain has been removed and " "is no longer registered to your organization."
        dns_needed_text = "Before this domain can be used, " "you’ll need to add name server addresses."
        ready_text = "This domain has name servers and is ready for use."
        on_hold_text = (
            "This domain is administratively paused, "
            "so it can’t be edited and won’t resolve in DNS. "
            "Contact help@get.gov for details."
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

                # Grab the home page
                response = self.client.get("/")

                # Make sure the user can actually see the domain.
                # We expect two instances because of SR content.
                self.assertContains(response, domain_name, count=2)

                # Check that we have the right text content.
                self.assertContains(response, expected_message, count=1)

                # Delete the role and domain to ensure we're testing in isolation
                user_role.delete()
                test_domain.delete()

    def test_state_help_text_expired(self):
        """Tests if each domain state has help text when expired"""
        expired_text = "This domain has expired, but it is still online. " "To renew this domain, contact help@get.gov."
        test_domain, _ = Domain.objects.get_or_create(name="expired.gov", state=Domain.State.READY)
        test_domain.expiration_date = date(2011, 10, 10)
        test_domain.save()

        UserDomainRole.objects.get_or_create(user=self.user, domain=test_domain, role=UserDomainRole.Roles.MANAGER)

        # Grab the home page
        response = self.client.get("/")

        # Make sure the user can actually see the domain.
        # We expect two instances because of SR content.
        self.assertContains(response, "expired.gov", count=2)

        # Check that we have the right text content.
        self.assertContains(response, expired_text, count=1)

    def test_state_help_text_no_expiration_date(self):
        """Tests if each domain state has help text when expiration date is None"""

        # == Test a expiration of None for state ready. This should be expired. == #
        expired_text = "This domain has expired, but it is still online. " "To renew this domain, contact help@get.gov."
        test_domain, _ = Domain.objects.get_or_create(name="imexpired.gov", state=Domain.State.READY)
        test_domain.expiration_date = None
        test_domain.save()

        UserDomainRole.objects.get_or_create(user=self.user, domain=test_domain, role=UserDomainRole.Roles.MANAGER)

        # Grab the home page
        response = self.client.get("/")

        # Make sure the user can actually see the domain.
        # We expect two instances because of SR content.
        self.assertContains(response, "imexpired.gov", count=2)

        # Make sure the expiration date is None
        self.assertEqual(test_domain.expiration_date, None)

        # Check that we have the right text content.
        self.assertContains(response, expired_text, count=1)

        # == Test a expiration of None for state unknown. This should not display expired text. == #
        unknown_text = "Before this domain can be used, " "you’ll need to add name server addresses."
        test_domain_2, _ = Domain.objects.get_or_create(name="notexpired.gov", state=Domain.State.UNKNOWN)
        test_domain_2.expiration_date = None
        test_domain_2.save()

        UserDomainRole.objects.get_or_create(user=self.user, domain=test_domain_2, role=UserDomainRole.Roles.MANAGER)

        # Grab the home page
        response = self.client.get("/")

        # Make sure the user can actually see the domain.
        # We expect two instances because of SR content.
        self.assertContains(response, "notexpired.gov", count=2)

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

        # Ensure that igorville.gov exists on the page
        home_page = self.client.get("/")
        self.assertContains(home_page, "igorville.gov")

        # Check if the delete button exists. We can do this by checking for its id and text content.
        self.assertContains(home_page, "Delete")
        self.assertContains(home_page, "button-toggle-delete-domain-alert-1")

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

        # Ensure that igorville.gov exists on the page
        home_page = self.client.get("/")
        self.assertContains(home_page, "igorville.gov")

        # Check if the delete button exists. We can do this by checking for its id and text content.
        self.assertContains(home_page, "Delete")
        self.assertContains(home_page, "button-toggle-delete-domain-alert-1")

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


class FinishUserProfileTests(TestWithUser, WebTest):
    """A series of tests that target the finish setup page for user profile"""

    # csrf checks do not work well with WebTest.
    # We disable them here.
    csrf_checks = False

    def setUp(self):
        super().setUp()
        self.user.title = None
        self.user.save()
        self.client.force_login(self.user)
        self.domain, _ = Domain.objects.get_or_create(name="sampledomain.gov", state=Domain.State.READY)
        self.role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=self.domain, role=UserDomainRole.Roles.MANAGER
        )

    def tearDown(self):
        super().tearDown()
        PublicContact.objects.filter(domain=self.domain).delete()
        self.role.delete()
        self.domain.delete()
        Domain.objects.all().delete()
        Website.objects.all().delete()
        Contact.objects.all().delete()

    def _set_session_cookie(self):
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

    def _submit_form_webtest(self, form, follow=False):
        page = form.submit()
        self._set_session_cookie()
        return page.follow() if follow else page

    @less_console_noise_decorator
    def test_new_user_with_profile_feature_on(self):
        """Tests that a new user is redirected to the profile setup page when profile_feature is on"""
        self.app.set_user(self.incomplete_user.username)
        with override_flag("profile_feature", active=True):
            # This will redirect the user to the setup page.
            # Follow implicity checks if our redirect is working.
            finish_setup_page = self.app.get(reverse("home")).follow()
            self._set_session_cookie()

            # Assert that we're on the right page
            self.assertContains(finish_setup_page, "Finish setting up your profile")

            finish_setup_page = self._submit_form_webtest(finish_setup_page.form)

            self.assertEqual(finish_setup_page.status_code, 200)

            # We're missing a phone number, so the page should tell us that
            self.assertContains(finish_setup_page, "Enter your phone number.")

            # Check for the name of the save button
            self.assertContains(finish_setup_page, "contact_setup_save_button")

            # Add a phone number
            finish_setup_form = finish_setup_page.form
            finish_setup_form["phone"] = "(201) 555-0123"
            finish_setup_form["title"] = "CEO"
            finish_setup_form["last_name"] = "example"
            save_page = self._submit_form_webtest(finish_setup_form, follow=True)

            self.assertEqual(save_page.status_code, 200)
            self.assertContains(save_page, "Your profile has been updated.")

            # Try to navigate back to the home page.
            # This is the same as clicking the back button.
            completed_setup_page = self.app.get(reverse("home"))
            self.assertContains(completed_setup_page, "Manage your domain")

    @less_console_noise_decorator
    def test_new_user_goes_to_domain_request_with_profile_feature_on(self):
        """Tests that a new user is redirected to the domain request page when profile_feature is on"""

        self.app.set_user(self.incomplete_user.username)
        with override_flag("profile_feature", active=True):
            # This will redirect the user to the setup page
            finish_setup_page = self.app.get(reverse("domain-request:")).follow()
            self._set_session_cookie()

            # Assert that we're on the right page
            self.assertContains(finish_setup_page, "Finish setting up your profile")

            finish_setup_page = self._submit_form_webtest(finish_setup_page.form)

            self.assertEqual(finish_setup_page.status_code, 200)

            # We're missing a phone number, so the page should tell us that
            self.assertContains(finish_setup_page, "Enter your phone number.")

            # Check for the name of the save button
            self.assertContains(finish_setup_page, "contact_setup_save_button")

            # Add a phone number
            finish_setup_form = finish_setup_page.form
            finish_setup_form["phone"] = "(201) 555-0123"
            finish_setup_form["title"] = "CEO"
            finish_setup_form["last_name"] = "example"
            completed_setup_page = self._submit_form_webtest(finish_setup_page.form, follow=True)

            self.assertEqual(completed_setup_page.status_code, 200)
            # Assert that we're on the domain request page
            self.assertContains(completed_setup_page, "How we’ll reach you")
            self.assertContains(completed_setup_page, "Your contact information")

    @less_console_noise_decorator
    def test_new_user_with_profile_feature_off(self):
        """Tests that a new user is not redirected to the profile setup page when profile_feature is off"""
        with override_flag("profile_feature", active=False):
            response = self.client.get("/")
        self.assertNotContains(response, "Finish setting up your profile")

    @less_console_noise_decorator
    def test_new_user_goes_to_domain_request_with_profile_feature_off(self):
        """Tests that a new user is redirected to the domain request page
        when profile_feature is off but not the setup page"""
        with override_flag("profile_feature", active=False):
            response = self.client.get("/request/")
        self.assertContains(response, "How we’ll reach you")
        self.assertContains(response, "Your contact information")


class UserProfileTests(TestWithUser, WebTest):
    """A series of tests that target your profile functionality"""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.domain, _ = Domain.objects.get_or_create(name="sampledomain.gov", state=Domain.State.READY)
        self.role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=self.domain, role=UserDomainRole.Roles.MANAGER
        )

    def tearDown(self):
        super().tearDown()
        PublicContact.objects.filter(domain=self.domain).delete()
        self.role.delete()
        self.domain.delete()
        Contact.objects.all().delete()

    @less_console_noise_decorator
    def error_500_main_nav_with_profile_feature_turned_on(self):
        """test that Your profile is in main nav of 500 error page when profile_feature is on.

        Our treatment of 401 and 403 error page handling with that waffle feature is similar, so we
        assume that the same test results hold true for 401 and 403."""
        with override_flag("profile_feature", active=True):
            with self.assertRaises(Exception):
                response = self.client.get(reverse("home"), follow=True)
                self.assertEqual(response.status_code, 500)
                self.assertContains(response, "Your profile")

    @less_console_noise_decorator
    def error_500_main_nav_with_profile_feature_turned_off(self):
        """test that Your profile is not in main nav of 500 error page when profile_feature is off.

        Our treatment of 401 and 403 error page handling with that waffle feature is similar, so we
        assume that the same test results hold true for 401 and 403."""
        with override_flag("profile_feature", active=False):
            with self.assertRaises(Exception):
                response = self.client.get(reverse("home"), follow=True)
                self.assertEqual(response.status_code, 500)
                self.assertNotContains(response, "Your profile")

    @less_console_noise_decorator
    def test_home_page_main_nav_with_profile_feature_on(self):
        """test that Your profile is in main nav of home page when profile_feature is on"""
        with override_flag("profile_feature", active=True):
            response = self.client.get("/", follow=True)
        self.assertContains(response, "Your profile")

    @less_console_noise_decorator
    def test_home_page_main_nav_with_profile_feature_off(self):
        """test that Your profile is not in main nav of home page when profile_feature is off"""
        with override_flag("profile_feature", active=False):
            response = self.client.get("/", follow=True)
        self.assertNotContains(response, "Your profile")

    @less_console_noise_decorator
    def test_new_request_main_nav_with_profile_feature_on(self):
        """test that Your profile is in main nav of new request when profile_feature is on"""
        with override_flag("profile_feature", active=True):
            response = self.client.get("/request/", follow=True)
        self.assertContains(response, "Your profile")

    @less_console_noise_decorator
    def test_new_request_main_nav_with_profile_feature_off(self):
        """test that Your profile is not in main nav of new request when profile_feature is off"""
        with override_flag("profile_feature", active=False):
            response = self.client.get("/request/", follow=True)
        self.assertNotContains(response, "Your profile")

    @less_console_noise_decorator
    def test_user_profile_main_nav_with_profile_feature_on(self):
        """test that Your profile is in main nav of user profile when profile_feature is on"""
        with override_flag("profile_feature", active=True):
            response = self.client.get("/user-profile", follow=True)
        self.assertContains(response, "Your profile")

    @less_console_noise_decorator
    def test_user_profile_returns_404_when_feature_off(self):
        """test that Your profile returns 404 when profile_feature is off"""
        with override_flag("profile_feature", active=False):
            response = self.client.get("/user-profile", follow=True)
        self.assertEqual(response.status_code, 404)

    @less_console_noise_decorator
    def test_domain_detail_profile_feature_on(self):
        """test that domain detail view when profile_feature is on"""
        with override_flag("profile_feature", active=True):
            response = self.client.get(reverse("domain", args=[self.domain.pk]), follow=True)
        self.assertContains(response, "Your profile")
        self.assertNotContains(response, "Your contact information")

    @less_console_noise_decorator
    def test_domain_your_contact_information_when_profile_feature_off(self):
        """test that Your contact information is accessible when profile_feature is off"""
        with override_flag("profile_feature", active=False):
            response = self.client.get(f"/domain/{self.domain.id}/your-contact-information", follow=True)
        self.assertContains(response, "Your contact information")

    @less_console_noise_decorator
    def test_domain_your_contact_information_when_profile_feature_on(self):
        """test that Your contact information is not accessible when profile feature is on"""
        with override_flag("profile_feature", active=True):
            response = self.client.get(f"/domain/{self.domain.id}/your-contact-information", follow=True)
        self.assertEqual(response.status_code, 404)

    @less_console_noise_decorator
    def test_request_when_profile_feature_on(self):
        """test that Your profile is in request page when profile feature is on"""

        contact_user, _ = Contact.objects.get_or_create(user=self.user)
        site = DraftDomain.objects.create(name="igorville.gov")
        domain_request = DomainRequest.objects.create(
            creator=self.user,
            requested_domain=site,
            status=DomainRequest.DomainRequestStatus.SUBMITTED,
            authorizing_official=contact_user,
            submitter=contact_user,
        )
        with override_flag("profile_feature", active=True):
            response = self.client.get(f"/domain-request/{domain_request.id}", follow=True)
            self.assertContains(response, "Your profile")
            response = self.client.get(f"/domain-request/{domain_request.id}/withdraw", follow=True)
            self.assertContains(response, "Your profile")
        # cleanup
        domain_request.delete()
        site.delete()

    @less_console_noise_decorator
    def test_request_when_profile_feature_off(self):
        """test that Your profile is not in request page when profile feature is off"""

        contact_user, _ = Contact.objects.get_or_create(user=self.user)
        site = DraftDomain.objects.create(name="igorville.gov")
        domain_request = DomainRequest.objects.create(
            creator=self.user,
            requested_domain=site,
            status=DomainRequest.DomainRequestStatus.SUBMITTED,
            authorizing_official=contact_user,
            submitter=contact_user,
        )
        with override_flag("profile_feature", active=False):
            response = self.client.get(f"/domain-request/{domain_request.id}", follow=True)
            self.assertNotContains(response, "Your profile")
            response = self.client.get(f"/domain-request/{domain_request.id}/withdraw", follow=True)
            self.assertNotContains(response, "Your profile")
        # cleanup
        domain_request.delete()
        site.delete()

    @less_console_noise_decorator
    def test_user_profile_form_submission(self):
        """test user profile form submission"""
        self.app.set_user(self.user.username)
        with override_flag("profile_feature", active=True):
            profile_page = self.app.get(reverse("user-profile")).follow()
            session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
            self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
            profile_form = profile_page.form
            profile_page = profile_form.submit()

            self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

            profile_form = profile_page.form
            profile_form["title"] = "sample title"
            profile_form["phone"] = "(201) 555-1212"
            profile_page = profile_form.submit()
            self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
            profile_page = profile_page.follow()
            self.assertEqual(profile_page.status_code, 200)
            self.assertContains(profile_page, "Your profile has been updated")
