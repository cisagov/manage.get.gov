from datetime import date, timedelta
from django.test import Client, TestCase, override_settings
from django.contrib.auth import get_user_model
from django_webtest import WebTest  # type: ignore
from django.conf import settings

from api.tests.common import less_console_noise_decorator
from registrar.models.contact import Contact
from registrar.models.domain import Domain
from registrar.models.draft_domain import DraftDomain
from registrar.models.federal_agency import FederalAgency
from registrar.models.portfolio import Portfolio
from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.public_contact import PublicContact
from registrar.models.user import User
from registrar.models.user_domain_role import UserDomainRole
from registrar.models.utility.portfolio_helper import UserPortfolioRoleChoices
from registrar.views.domain import DomainNameserversView
from .common import MockEppLib, create_test_user, less_console_noise  # type: ignore
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
        super().setUp()
        self.client = Client()

    @less_console_noise_decorator
    def test_home_page(self):
        """Home page should NOT be available without a login."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)

    @less_console_noise_decorator
    def test_health_check_endpoint(self):
        response = self.client.get("/health")
        self.assertContains(response, "OK", status_code=200)
    
    @less_console_noise_decorator
    def test_domain_request_form_not_logged_in(self):
        """Domain request form not accessible without a logged-in user."""
        response = self.client.get(reverse("domain-request:start"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login?next=/request/start/", response.headers["Location"])


class TestHealthPageView(TestCase):
    def setUp(self):
        self.client = Client()
        return super().setUp()

    @patch.dict("os.environ", {"GIT_BRANCH": "main", "GIT_COMMIT": "abcdef123456", "GIT_TAG": "v1.0.0"})
    def test_health_contains_git_info(self):
        response = self.client.get("/version")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "main")
        self.assertContains(response, "abcdef123456")
        self.assertContains(response, "v1.0.0")

    @patch.dict(
        "os.environ",
        {
            "GIT_BRANCH": "another-branch",
            "GIT_COMMIT_SHA": "bcdefg234567",
        },
    )
    def test_healh_contains_git_info_without_tag(self):
        response = self.client.get("/version")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "another-branch")
        self.assertContains(response, "bcdefg234567")
        self.assertNotContains(response, "Git tag")


class TestWithUser(MockEppLib):
    """Class for executing tests with a test user.
    Note that tests share the test user within their test class, so the user
    cannot be changed within a test."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = create_test_user()

    def setUp(self):
        super().setUp()
        self.client = Client()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        User.objects.all().delete()


class TestEnvironmentVariablesEffects(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = create_test_user()

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def tearDown(self):
        super().tearDown()
        UserDomainRole.objects.all().delete()
        Domain.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        User.objects.all().delete()

    @less_console_noise_decorator
    @override_settings(IS_PRODUCTION=True)
    def test_production_environment(self):
        """No banner on prod."""
        home_page = self.client.get("/")
        self.assertNotContains(home_page, "You are on a test site.")

    @less_console_noise_decorator
    @override_settings(IS_PRODUCTION=False)
    def test_non_production_environment(self):
        """Banner on non-prod."""
        home_page = self.client.get("/")
        self.assertContains(home_page, "You are on a test site.")

    @less_console_noise_decorator
    def side_effect_raise_value_error(self):
        """Side effect that raises a 500 error"""
        raise ValueError("Some error")

    @less_console_noise_decorator
    @override_settings(IS_PRODUCTION=False)
    def test_non_production_environment_raises_500_and_shows_banner(self):
        """Tests if the non-prod banner is still shown on a 500"""
        fake_domain, _ = Domain.objects.get_or_create(name="igorville.gov")

        # Add a role
        UserDomainRole.objects.get_or_create(user=self.user, domain=fake_domain, role=UserDomainRole.Roles.MANAGER)

        with patch.object(DomainNameserversView, "get_initial", side_effect=self.side_effect_raise_value_error):
            with self.assertRaises(ValueError):
                contact_page_500 = self.client.get(
                    reverse("domain-dns-nameservers", kwargs={"domain_pk": fake_domain.id}),
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
        UserDomainRole.objects.get_or_create(user=self.user, domain=fake_domain, role=UserDomainRole.Roles.MANAGER)

        with patch.object(DomainNameserversView, "get_initial", side_effect=self.side_effect_raise_value_error):
            with self.assertRaises(ValueError):
                contact_page_500 = self.client.get(
                    reverse("domain-dns-nameservers", kwargs={"domain_pk": fake_domain.id}),
                )

                # Check that a 500 response is returned
                self.assertEqual(contact_page_500.status_code, 500)

                self.assertNotContains(contact_page_500, "You are on a test site.")


class HomeTests(TestWithUser):
    """A series of tests that target the two tables on home.html"""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    @less_console_noise_decorator
    def test_empty_domain_table(self):
        response = self.client.get("/")
        self.assertContains(response, "You don't have any registered domains.")
        self.assertContains(response, "Why don't I see my domain when I sign in to the registrar?")

    @less_console_noise_decorator
    def test_state_help_text(self):
        """Tests if each domain state has help text"""

        # Get the expected text content of each state
        deleted_text = "This domain has been removed and " "is no longer registered to your organization."
        dns_needed_text = "Before this domain can be used, "
        ready_text = "This domain has name servers and is ready for use."
        on_hold_text = "This domain is administratively paused, "
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
                test_domain.expiration_date = date.today() + timedelta(days=61)
                test_domain.save()

                user_role, _ = UserDomainRole.objects.get_or_create(
                    user=self.user, domain=test_domain, role=UserDomainRole.Roles.MANAGER
                )

                # Grab the json response for domain list
                response = self.client.get("/get-domains-json/")

                # Make sure the domain is in the list.
                self.assertContains(response, domain_name, count=1)

                # Check that we have the right text content.
                self.assertContains(response, expected_message, count=1)

                # Delete the role and domain to ensure we're testing in isolation
                user_role.delete()
                test_domain.delete()

    @less_console_noise_decorator
    def test_state_help_text_expired(self):
        """Tests if each domain state has help text when expired"""
        expired_text = "This domain has expired. "
        test_domain, _ = Domain.objects.get_or_create(name="expired.gov", state=Domain.State.READY)
        test_domain.expiration_date = date(2011, 10, 10)
        test_domain.save()

        test_role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=test_domain, role=UserDomainRole.Roles.MANAGER
        )

        # Grab the json response of the domains list
        response = self.client.get("/get-domains-json/")

        # Make sure the domain is in the response
        self.assertContains(response, "expired.gov", count=1)

        # Check that we have the right text content.
        self.assertContains(response, expired_text, count=1)

        test_role.delete()
        test_domain.delete()

    @less_console_noise_decorator
    def test_state_help_text_is_expiring(self):
        """Tests if each domain state has help text when expired"""
        is_expiring_text = "This domain is expiring soon"
        test_domain, _ = Domain.objects.get_or_create(name="is-expiring.gov", state=Domain.State.READY)
        test_domain.expiration_date = date.today()
        test_domain.save()

        test_role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=test_domain, role=UserDomainRole.Roles.MANAGER
        )

        # Grab the json response of the domains list
        response = self.client.get("/get-domains-json/")

        # Make sure the domain is in the response
        self.assertContains(response, "is-expiring.gov", count=1)

        # Check that we have the right text content.
        self.assertContains(response, is_expiring_text, count=1)

        test_role.delete()
        test_domain.delete()

    @less_console_noise_decorator
    def test_state_help_text_no_expiration_date(self):
        """Tests if each domain state has help text when expiration date is None"""

        # == Test a expiration of None for state ready. This should be expired. == #
        expired_text = "This domain has expired. "
        test_domain, _ = Domain.objects.get_or_create(name="imexpired.gov", state=Domain.State.READY)
        test_domain.expiration_date = None
        test_domain.save()

        UserDomainRole.objects.get_or_create(user=self.user, domain=test_domain, role=UserDomainRole.Roles.MANAGER)

        # Grab the json response of the domains list
        response = self.client.get("/get-domains-json/")

        # Make sure domain is in the response
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

        # Grab the json response of the domains list
        response = self.client.get("/get-domains-json/")

        # Make sure the response contains the domain
        self.assertContains(response, "notexpired.gov", count=1)

        # Make sure the expiration date is None
        self.assertEqual(test_domain_2.expiration_date, None)

        # Check that we have the right text content.
        self.assertContains(response, unknown_text, count=1)

        UserDomainRole.objects.all().delete()
        Domain.objects.all().delete()

    @less_console_noise_decorator
    def test_home_deletes_withdrawn_domain_request(self):
        """Tests if the user can delete a DomainRequest in the 'withdrawn' status"""

        site = DraftDomain.objects.create(name="igorville.gov")
        domain_request = DomainRequest.objects.create(
            requester=self.user, requested_domain=site, status=DomainRequest.DomainRequestStatus.WITHDRAWN
        )

        # Trigger the delete logic
        response = self.client.post(
            reverse("domain-request-delete", kwargs={"domain_request_pk": domain_request.pk}), follow=True
        )

        self.assertNotContains(response, "igorville.gov")

        # clean up
        domain_request.delete()

    @less_console_noise_decorator
    def test_home_deletes_started_domain_request(self):
        """Tests if the user can delete a DomainRequest in the 'started' status"""

        site = DraftDomain.objects.create(name="igorville.gov")
        domain_request = DomainRequest.objects.create(
            requester=self.user, requested_domain=site, status=DomainRequest.DomainRequestStatus.STARTED
        )

        # Trigger the delete logic
        response = self.client.post(
            reverse("domain-request-delete", kwargs={"domain_request_pk": domain_request.pk}), follow=True
        )

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
                            requester=self.user, requested_domain=draft_domain, status=status
                        )

                        # Trigger the delete logic
                        response = self.client.post(
                            reverse("domain-request-delete", kwargs={"domain_request_pk": domain_request.pk}),
                            follow=True,
                        )

                        # Check for a 403 error - the end user should not be allowed to do this
                        self.assertEqual(response.status_code, 403)

                        desired_domain_request = DomainRequest.objects.filter(requested_domain=draft_domain)

                        # Make sure the DomainRequest wasn't deleted
                        self.assertEqual(desired_domain_request.count(), 1)

                        # clean up
                        domain_request.delete()

    @less_console_noise_decorator
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

        site = DraftDomain.objects.create(name="igorville.gov")
        domain_request = DomainRequest.objects.create(
            requester=self.user,
            requested_domain=site,
            status=DomainRequest.DomainRequestStatus.WITHDRAWN,
            senior_official=contact,
        )
        domain_request.other_contacts.set([contact_2])

        # Create a second domain request to attach contacts to
        site_2 = DraftDomain.objects.create(name="teaville.gov")
        domain_request_2 = DomainRequest.objects.create(
            requester=self.user,
            requested_domain=site_2,
            status=DomainRequest.DomainRequestStatus.STARTED,
            senior_official=contact_2,
        )
        domain_request_2.other_contacts.set([contact_shared])

        igorville = DomainRequest.objects.filter(requested_domain__name="igorville.gov")
        self.assertTrue(igorville.exists())

        # Trigger the delete logic
        self.client.post(reverse("domain-request-delete", kwargs={"domain_request_pk": domain_request.pk}))

        # igorville is now deleted
        igorville = DomainRequest.objects.filter(requested_domain__name="igorville.gov")
        self.assertFalse(igorville.exists())

        # Check if the orphaned contacts were deleted
        orphan = Contact.objects.filter(id=contact.id)
        self.assertFalse(orphan.exists())

        try:
            edge_case = Contact.objects.filter(id=contact_2.id).get()
        except Contact.DoesNotExist:
            self.fail("contact_2 (a non-orphaned contact) was deleted")

        self.assertEqual(edge_case, contact_2)

        DomainRequest.objects.all().delete()
        Contact.objects.all().delete()

    @less_console_noise_decorator
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
        contact_user, _ = Contact.objects.get_or_create(
            first_name="Hank",
            last_name="McFakey",
        )

        site = DraftDomain.objects.create(name="igorville.gov")
        domain_request = DomainRequest.objects.create(
            requester=self.user,
            requested_domain=site,
            status=DomainRequest.DomainRequestStatus.WITHDRAWN,
            senior_official=contact,
        )
        domain_request.other_contacts.set([contact_2])

        # Create a second domain request to attach contacts to
        site_2 = DraftDomain.objects.create(name="teaville.gov")
        domain_request_2 = DomainRequest.objects.create(
            requester=self.user,
            requested_domain=site_2,
            status=DomainRequest.DomainRequestStatus.STARTED,
            senior_official=contact_2,
        )
        domain_request_2.other_contacts.set([contact_shared])

        teaville = DomainRequest.objects.filter(requested_domain__name="teaville.gov")
        self.assertTrue(teaville.exists())

        # Trigger the delete logic
        self.client.post(reverse("domain-request-delete", kwargs={"domain_request_pk": domain_request_2.pk}))

        teaville = DomainRequest.objects.filter(requested_domain__name="teaville.gov")
        self.assertFalse(teaville.exists())

        # Check if the orphaned contact was deleted
        orphan = Contact.objects.filter(id=contact_shared.id)
        self.assertFalse(orphan.exists())

        DomainRequest.objects.all().delete()
        Contact.objects.all().delete()

    @less_console_noise_decorator
    def test_domain_request_form_view(self):
        response = self.client.get(reverse("domain-request:start"), follow=True)
        self.assertContains(
            response,
            "You’re about to start your .gov domain request.",
        )

    @less_console_noise_decorator
    def test_domain_request_form_with_ineligible_user(self):
        """Domain request form not accessible for an ineligible user.
        This test should be solid enough since all domain request wizard
        views share the same permissions class"""
        username = "restricted_user"
        first_name = "First"
        last_name = "Last"
        email = "restricted@example.com"
        phone = "8003111234"
        status = User.RESTRICTED
        restricted_user = get_user_model().objects.create(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            status=status,
            title="title",
        )
        self.client.force_login(restricted_user)
        response = self.client.get(reverse("domain-request:start"), follow=True)
        self.assertEqual(response.status_code, 403)
        restricted_user.delete()


class FinishUserProfileTests(TestWithUser, WebTest):
    """A series of tests that target the finish setup page for user profile"""

    # csrf checks do not work well with WebTest.
    # We disable them here.
    csrf_checks = False

    def setUp(self):
        super().setUp()
        self.initial_user_title = self.user.title
        self.user.title = None
        self.user.save()
        self.client.force_login(self.user)
        self.domain, _ = Domain.objects.get_or_create(name="sampledomain.gov", state=Domain.State.READY)
        self.role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=self.domain, role=UserDomainRole.Roles.MANAGER
        )

    def tearDown(self):
        super().tearDown()
        DomainRequest.objects.all().delete()
        DomainInformation.objects.all().delete()
        self.user.title = self.initial_user_title
        self.user.save()
        PublicContact.objects.filter(domain=self.domain).delete()
        self.role.delete()
        self.domain.delete()
        Domain.objects.all().delete()
        Website.objects.all().delete()
        Contact.objects.all().delete()

    def _set_session_cookie(self):
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

    def _submit_form_webtest(self, form, follow=False, name=None):
        if name:
            page = form.submit(name=name)
        else:
            page = form.submit()
        self._set_session_cookie()
        return page.follow() if follow else page

    @less_console_noise_decorator
    def test_full_name_initial_value(self):
        """Test that full_name initial value is empty when first_name or last_name is empty.
        This will later be displayed as "unknown" using javascript."""
        username_regular_incomplete = "test_regular_user_incomplete"
        first_name_2 = "Incomplete"
        email_2 = "unicorn@igorville.com"
        incomplete_regular_user = get_user_model().objects.create(
            username=username_regular_incomplete,
            first_name=first_name_2,
            email=email_2,
            verification_type=User.VerificationTypeChoices.REGULAR,
        )
        self.app.set_user(incomplete_regular_user.username)

        # Test when first_name is empty
        incomplete_regular_user.first_name = ""
        incomplete_regular_user.last_name = "Doe"
        incomplete_regular_user.save()

        finish_setup_page = self.app.get(reverse("home")).follow()
        form = finish_setup_page.form
        self.assertEqual(form["full_name"].value, "")

        # Test when last_name is empty
        incomplete_regular_user.first_name = "John"
        incomplete_regular_user.last_name = ""
        incomplete_regular_user.save()

        finish_setup_page = self.app.get(reverse("home")).follow()
        form = finish_setup_page.form
        self.assertEqual(form["full_name"].value, "")

        # Test when both first_name and last_name are empty
        incomplete_regular_user.first_name = ""
        incomplete_regular_user.last_name = ""
        incomplete_regular_user.save()

        finish_setup_page = self.app.get(reverse("home")).follow()
        form = finish_setup_page.form
        self.assertEqual(form["full_name"].value, "")

        # Test when both first_name and last_name are present
        incomplete_regular_user.first_name = "John"
        incomplete_regular_user.last_name = "Doe"
        incomplete_regular_user.save()

        finish_setup_page = self.app.get(reverse("home")).follow()
        form = finish_setup_page.form
        self.assertEqual(form["full_name"].value, "John Doe")

        incomplete_regular_user.delete()

    @less_console_noise_decorator
    def test_new_user(self):
        """Tests that a new user is redirected to the profile setup page"""
        username_regular_incomplete = "test_regular_user_incomplete"
        first_name_2 = "Incomplete"
        email_2 = "unicorn@igorville.com"
        # in the case below, REGULAR user is 'Verified by Login.gov, ie. IAL2
        incomplete_regular_user = get_user_model().objects.create(
            username=username_regular_incomplete,
            first_name=first_name_2,
            email=email_2,
            verification_type=User.VerificationTypeChoices.REGULAR,
        )

        self.app.set_user(incomplete_regular_user.username)
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
        self.assertContains(finish_setup_page, "user_setup_save_button")

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
        incomplete_regular_user.delete()

    @less_console_noise_decorator
    def test_new_user_with_empty_name_can_add_name(self):
        """Tests that a new user without a name can still enter this information accordingly"""
        username_regular_incomplete = "test_regular_user_incomplete"
        email = "unicorn@igorville.com"
        # in the case below, REGULAR user is 'Verified by Login.gov, ie. IAL2
        incomplete_regular_user = get_user_model().objects.create(
            username=username_regular_incomplete,
            first_name="",
            last_name="",
            email=email,
            verification_type=User.VerificationTypeChoices.REGULAR,
        )
        self.app.set_user(incomplete_regular_user.username)
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
        self.assertContains(finish_setup_page, "user_setup_save_button")

        # Add a phone number
        finish_setup_form = finish_setup_page.form
        finish_setup_form["first_name"] = "test"
        finish_setup_form["last_name"] = "test2"
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
        incomplete_regular_user.delete()

    @less_console_noise_decorator
    def test_new_user_goes_to_domain_request(self):
        """Tests that a new user is redirected to the domain request page"""
        username_regular_incomplete = "test_regular_user_incomplete"
        first_name_2 = "Incomplete"
        email_2 = "unicorn@igorville.com"
        # in the case below, REGULAR user is 'Verified by Login.gov, ie. IAL2
        incomplete_regular_user = get_user_model().objects.create(
            username=username_regular_incomplete,
            first_name=first_name_2,
            email=email_2,
            verification_type=User.VerificationTypeChoices.REGULAR,
        )
        self.app.set_user(incomplete_regular_user.username)
        with override_flag("", active=True):
            # This will redirect the user to the setup page
            finish_setup_page = self.app.get(reverse("domain-request:start")).follow()
            self._set_session_cookie()

            # Assert that we're on the right page
            self.assertContains(finish_setup_page, "Finish setting up your profile")

            finish_setup_page = self._submit_form_webtest(finish_setup_page.form)

            self.assertEqual(finish_setup_page.status_code, 200)

            # We're missing a phone number, so the page should tell us that
            self.assertContains(finish_setup_page, "Enter your phone number.")

            # Check for the name of the save button
            self.assertContains(finish_setup_page, "user_setup_save_button")

            # Add a phone number
            finish_setup_form = finish_setup_page.form
            finish_setup_form["first_name"] = "firstname"
            finish_setup_form["phone"] = "(201) 555-0123"
            finish_setup_form["title"] = "CEO"
            finish_setup_form["last_name"] = "example"
            completed_setup_page = self._submit_form_webtest(finish_setup_page.form, follow=True)

            self.assertEqual(completed_setup_page.status_code, 200)

            finish_setup_form = completed_setup_page.form

            # Submit the form using the specific submit button to execute the redirect
            completed_setup_page = self._submit_form_webtest(
                finish_setup_form, follow=True, name="user_setup_submit_button"
            )
            self.assertEqual(completed_setup_page.status_code, 200)

            # Assert that we are still on the
            # Assert that we're on the domain request page
            self.assertNotContains(completed_setup_page, "Finish setting up your profile")
            self.assertNotContains(completed_setup_page, "What contact information should we use to reach you?")

            self.assertContains(completed_setup_page, "You’re about to start your .gov domain request")
        incomplete_regular_user.delete()

    def assert_basic_header(self, page):
        self.assertContains(page, "usa-header--basic")
        self.assertNotContains(page, "usa-header--extended")

    @less_console_noise_decorator
    def test_finish_setup_uses_basic_header_for_new_user_flag_on(self):
        user = get_user_model().objects.create(
            username="test_finish_setup_basic_header",
            first_name="New",
            last_name="",
            email="finish-setup-basic@igorville.com",
            verification_type=User.VerificationTypeChoices.REGULAR,
            title=None,
        )
        self.app.set_user(user.username)

        with override_flag("multiple_portfolios", active=True):
            page = self.app.get(reverse("home")).follow()
            self._set_session_cookie()

        self.assertContains(page, "Finish setting up your profile")
        self.assert_basic_header(page)

        user.delete()

    @less_console_noise_decorator
    def test_finish_setup_uses_basic_header_for_invited_user_flag_on(self):
        invited_user = get_user_model().objects.create(
            username="test_finish_setup_basic_header_invited",
            first_name="Invited",
            last_name="",
            email="finish-setup-invited@igorville.com",
            verification_type=User.VerificationTypeChoices.REGULAR,
            title=None,
        )

        portfolio, _ = Portfolio.objects.get_or_create(
            requester=self.user,
            organization_name="Test Organization",
        )

        PortfolioInvitation.objects.create(
            portfolio=portfolio,
            email=invited_user.email,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
        )

        self.app.set_user(invited_user.username)

        with override_flag("multiple_portfolios", active=True):
            page = self.app.get(reverse("home")).follow()
            self._set_session_cookie()

        self.assertContains(page, "Finish setting up your profile")
        self.assert_basic_header(page)

        PortfolioInvitation.objects.filter(portfolio=portfolio, email=invited_user.email).delete()
        invited_user.delete()

    @less_console_noise_decorator
    def test_finish_setup_does_not_render_extended_header_even_if_session_portfolio_is_set(self):
        user = get_user_model().objects.create(
            username="test_finish_setup_portfolio_in_session",
            first_name="New",
            last_name="",
            email="finish-setup-session@igorville.com",
            verification_type=User.VerificationTypeChoices.REGULAR,
            title=None,
        )

        portfolio, _ = Portfolio.objects.get_or_create(
            requester=self.user,
            organization_name="Session Org",
        )

        self.client.force_login(user)
        # simulate buggy state: portfolio present in session during setup
        session = self.client.session
        session["portfolio"] = portfolio
        session.save()

        with override_flag("multiple_portfolios", active=True):
            resp = self.client.get(reverse("finish-user-profile-setup"), follow=True)

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Finish setting up your profile")
        self.assert_basic_header(resp)

        user.delete()

    @less_console_noise_decorator
    def test_home_redirects_to_setup_and_renders_basic_header_for_unfinished_user_even_if_session_portfolio_set(self):
        unfinished_user = get_user_model().objects.create(
            username="test_unfinished_user_session_portfolio_basic_header",
            first_name="New",
            last_name="",
            email="unfinished-session@igorville.com",
            verification_type=User.VerificationTypeChoices.REGULAR,
            title=None,
        )

        portfolio, _ = Portfolio.objects.get_or_create(
            requester=self.user,
            organization_name="Session Org",
        )

        self.client.force_login(unfinished_user)

        session = self.client.session
        session["portfolio"] = portfolio
        session.save()

        with override_flag("multiple_portfolios", active=True):
            resp = self.client.get(reverse("home"), follow=True)

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Finish setting up your profile")
        self.assert_basic_header(resp)

        unfinished_user.delete()


class FinishUserProfileForOtherUsersTests(TestWithUser, WebTest):
    """A series of tests that target the user profile page intercept for incomplete IAL1 user profiles."""

    # csrf checks do not work well with WebTest.
    # We disable them here.
    csrf_checks = False

    def setUp(self):
        super().setUp()
        self.initial_user_title = self.user.title
        self.user.title = None
        self.user.save()
        self.client.force_login(self.user)
        self.domain, _ = Domain.objects.get_or_create(name="sampledomain.gov", state=Domain.State.READY)
        self.role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=self.domain, role=UserDomainRole.Roles.MANAGER
        )

    def tearDown(self):
        super().tearDown()
        self.user.title = self.initial_user_title
        self.user.save()
        PublicContact.objects.filter(domain=self.domain).delete()
        self.role.delete()
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
    def test_new_user(self):
        """Tests that a new user is redirected to the profile setup page,
        and testing that the confirmation modal is present"""
        username_other_incomplete = "test_other_user_incomplete"
        first_name_2 = "Incomplete"
        email_2 = "unicorn@igorville.com"
        # in the case below, other user is representative of GRANDFATHERED,
        # VERIFIED_BY_STAFF, INVITED, FIXTURE_USER, ie. IAL1
        incomplete_other_user = get_user_model().objects.create(
            username=username_other_incomplete,
            first_name=first_name_2,
            email=email_2,
            verification_type=User.VerificationTypeChoices.VERIFIED_BY_STAFF,
        )
        self.app.set_user(incomplete_other_user.username)
        # This will redirect the user to the user profile page.
        # Follow implicity checks if our redirect is working.
        user_profile_page = self.app.get(reverse("home")).follow()
        self._set_session_cookie()

        # Assert that we're on the right page by testing for the modal
        self.assertContains(user_profile_page, "domain registrants must maintain accurate contact information")

        user_profile_page = self._submit_form_webtest(user_profile_page.form)

        self.assertEqual(user_profile_page.status_code, 200)

        # Assert that modal does not appear on subsequent submits
        self.assertNotContains(user_profile_page, "domain registrants must maintain accurate contact information")
        # Assert that unique error message appears by testing the message in a specific div
        html_content = user_profile_page.content.decode("utf-8")
        # Normalize spaces and line breaks in the HTML content
        normalized_html_content = " ".join(html_content.split())
        # Expected string without extra spaces and line breaks
        expected_string = "Before you can manage your domain, we need you to add contact information."
        # Check for the presence of the <div> element with the specific text
        self.assertIn(f'<div class="usa-alert__body"> {expected_string} </div>', normalized_html_content)

        # We're missing a phone number, so the page should tell us that
        self.assertContains(user_profile_page, "Enter your phone number.")

        # We need to assert that links to manage your domain are not present (in both body and footer)
        self.assertNotContains(user_profile_page, "Manage your domains")
        # Assert the tooltip on the logo, indicating that the logo is not clickable
        self.assertContains(
            user_profile_page, 'title="Before you can manage your domains, we need you to add contact information."'
        )
        # Assert that modal does not appear on subsequent submits
        self.assertNotContains(user_profile_page, "domain registrants must maintain accurate contact information")

        # Add a phone number
        finish_setup_form = user_profile_page.form
        finish_setup_form["phone"] = "(201) 555-0123"
        finish_setup_form["title"] = "CEO"
        finish_setup_form["last_name"] = "example"
        save_page = self._submit_form_webtest(finish_setup_form, follow=True)

        self.assertEqual(save_page.status_code, 200)
        self.assertContains(save_page, "Your profile has been updated.")

        # We need to assert that logo is not clickable and links to manage your domain are not present
        # NOTE: "anage" is not a typo.  It is to accomodate the fact that the "m" is uppercase in one
        # instance and lowercase in the other.
        self.assertContains(save_page, "anage your domains", count=1)
        self.assertNotContains(save_page, "Before you can manage your domains, we need you to add contact information")
        # Assert that modal does not appear on subsequent submits
        self.assertNotContains(save_page, "domain registrants must maintain accurate contact information")

        # Try to navigate back to the home page.
        # This is the same as clicking the back button.
        completed_setup_page = self.app.get(reverse("home"))
        self.assertContains(completed_setup_page, "Manage your domain")


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
        DomainRequest.objects.all().delete()
        DraftDomain.objects.all().delete()
        Contact.objects.all().delete()
        DomainInformation.objects.all().delete()

    @less_console_noise_decorator
    def error_500_main_nav(self):
        """test that Your profile is in main nav of 500 error page.

        Our treatment of 401 and 403 error page handling with that waffle feature is similar, so we
        assume that the same test results hold true for 401 and 403."""
        with self.assertRaises(Exception):
            response = self.client.get(reverse("home"), follow=True)
            self.assertEqual(response.status_code, 500)
            self.assertContains(response, "Your profile")

    @less_console_noise_decorator
    def test_home_page_main_nav(self):
        """test that Your profile is in main nav of home page"""
        response = self.client.get("/", follow=True)
        self.assertContains(response, "Your profile")

    @less_console_noise_decorator
    def test_new_request_main_nav(self):
        """test that Your profile is in main nav of new request"""
        response = self.client.get(reverse("domain-request:start"), follow=True)
        self.assertContains(response, "Your profile")

    @less_console_noise_decorator
    def test_user_profile_main_nav(self):
        """test that Your profile is in main nav of user profile"""
        response = self.client.get("/user-profile", follow=True)
        self.assertContains(response, "Your profile")

    @less_console_noise_decorator
    def test_user_profile_back_button_when_coming_from_domain_request(self):
        """tests user profile,
        and when they are redirected from the domain request page"""
        response = self.client.get("/user-profile?redirect=domain-request:start")
        self.assertContains(response, "Your profile")
        self.assertContains(response, "Go back to your domain request")
        self.assertNotContains(response, "Back to manage your domains")

    @less_console_noise_decorator
    def test_domain_detail_contains_your_profile(self):
        """Tests that the domain detail view contains 'your profile' rather than 'your contact information'"""
        response = self.client.get(reverse("domain", kwargs={"domain_pk": self.domain.pk}))
        self.assertContains(response, "Your profile")
        self.assertNotContains(response, "Your contact information")

    @less_console_noise_decorator
    def test_domain_your_contact_information(self):
        """test that your contact information is not accessible"""
        response = self.client.get(f"/domain/{self.domain.id}/your-contact-information", follow=True)
        self.assertEqual(response.status_code, 404)

    @less_console_noise_decorator
    def test_profile_request_page(self):
        """test that your profile is in request"""

        contact_user, _ = Contact.objects.get_or_create(
            first_name="Hank",
            last_name="McFakerson",
        )
        site = DraftDomain.objects.create(name="igorville.gov")
        domain_request = DomainRequest.objects.create(
            requester=self.user,
            requested_domain=site,
            status=DomainRequest.DomainRequestStatus.SUBMITTED,
            senior_official=contact_user,
        )

        response = self.client.get(f"/domain-request/{domain_request.id}", follow=True)
        self.assertContains(response, "Your profile")
        response = self.client.get(f"/domain-request/{domain_request.id}/withdraw", follow=True)
        self.assertContains(response, "Your profile")

    @less_console_noise_decorator
    def test_user_profile_form_submission(self):
        """test user profile form submission"""
        self.app.set_user(self.user.username)
        profile_page = self.app.get(reverse("user-profile"))
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        profile_form = profile_page.form
        profile_form["title"] = "sample title"
        profile_form["phone"] = "(201) 555-1212"
        profile_page = profile_form.submit()
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
        profile_page = profile_page.follow()
        self.assertEqual(profile_page.status_code, 200)
        self.assertContains(profile_page, "Your profile has been updated")


class PortfoliosTests(TestWithUser, WebTest):
    """A series of tests that target the organizations"""

    # csrf checks do not work well with WebTest.
    # We disable them here.
    csrf_checks = False

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.domain, _ = Domain.objects.get_or_create(name="sampledomain.gov", state=Domain.State.READY)
        self.role, _ = UserDomainRole.objects.get_or_create(
            user=self.user, domain=self.domain, role=UserDomainRole.Roles.MANAGER
        )
        self.federal_agency = FederalAgency.objects.create()
        self.portfolio, _ = Portfolio.objects.get_or_create(
            requester=self.user, organization_name="xyz inc", federal_agency=self.federal_agency
        )

    def tearDown(self):
        Portfolio.objects.all().delete()
        self.federal_agency.delete()
        super().tearDown()
        PublicContact.objects.filter(domain=self.domain).delete()
        UserDomainRole.objects.all().delete()
        Domain.objects.all().delete()
        Website.objects.all().delete()
        Contact.objects.all().delete()

    def _set_session_cookie(self):
        session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
        self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)

    @less_console_noise_decorator
    def test_no_redirect_when_org_flag_false(self):
        """No redirect so no follow,
        implicitely test for the presense of the h2 by looking up its id"""
        self.app.set_user(self.user.username)
        home_page = self.app.get(reverse("home"))
        self._set_session_cookie()

        self.assertNotContains(home_page, self.portfolio.organization_name)

        self.assertContains(home_page, 'id="domain-requests-header"')

    @less_console_noise_decorator
    def test_no_redirect_when_user_has_no_portfolios(self):
        """No redirect so no follow,
        implicitly test for the presense of the h2 by looking up its id"""
        self.portfolio.delete()
        self.app.set_user(self.user.username)
        home_page = self.app.get(reverse("home"))
        self._set_session_cookie()

        self.assertNotContains(home_page, self.portfolio.organization_name)

        self.assertContains(home_page, 'id="domain-requests-header"')
