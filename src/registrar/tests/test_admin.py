from datetime import date, datetime
from django.utils import timezone
import re
from django.test import TestCase, RequestFactory, Client, override_settings
from django.contrib.admin.sites import AdminSite
from contextlib import ExitStack
from api.tests.common import less_console_noise_decorator
from django_webtest import WebTest  # type: ignore
from django.contrib import messages
from django.urls import reverse
from registrar.admin import (
    DomainAdmin,
    DomainRequestAdmin,
    DomainRequestAdminForm,
    DomainInvitationAdmin,
    ListHeaderAdmin,
    MyUserAdmin,
    AuditedAdmin,
    ContactAdmin,
    DomainInformationAdmin,
    MyHostAdmin,
    UserDomainRoleAdmin,
    VerifiedByStaffAdmin,
    FsmModelResource,
    WebsiteAdmin,
    DraftDomainAdmin,
    FederalAgencyAdmin,
    PublicContactAdmin,
    TransitionDomainAdmin,
    UserGroupAdmin,
)
from registrar.models import (
    Domain,
    DomainRequest,
    DomainInformation,
    DraftDomain,
    User,
    DomainInvitation,
    Contact,
    PublicContact,
    Host,
    Website,
    FederalAgency,
    UserGroup,
    TransitionDomain,
)
from registrar.models.user_domain_role import UserDomainRole
from registrar.models.verified_by_staff import VerifiedByStaff
from .common import (
    MockDb,
    MockSESClient,
    AuditedAdminMockData,
    completed_domain_request,
    generic_domain_object,
    less_console_noise,
    mock_user,
    create_superuser,
    create_user,
    create_ready_domain,
    multiple_unalphabetical_domain_objects,
    MockEppLib,
    GenericTestHelper,
)
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.auth import get_user_model
from unittest.mock import ANY, call, patch, Mock
from unittest import skip

from django.conf import settings
import boto3_mocking  # type: ignore
import logging

logger = logging.getLogger(__name__)


class TestFsmModelResource(TestCase):
    def setUp(self):
        self.resource = FsmModelResource()

    def test_init_instance(self):
        """Test initializing an instance of a class with a FSM field"""

        # Mock a row with FSMField data
        row_data = {"state": "ready"}

        self.resource._meta.model = Domain

        instance = self.resource.init_instance(row=row_data)

        # Assert that the instance is initialized correctly
        self.assertIsInstance(instance, Domain)
        self.assertEqual(instance.state, "ready")

    def test_import_field(self):
        """Test that importing a field does not import FSM field"""

        # Mock a FSMField and a non-FSM-field
        fsm_field_mock = Mock(attribute="state", column_name="state")
        field_mock = Mock(attribute="name", column_name="name")
        # Mock the data
        data_mock = {"state": "unknown", "name": "test"}
        # Define a mock Domain
        obj = Domain(state=Domain.State.UNKNOWN, name="test")

        # Mock the save() method of fields so that we can test if save is called
        # save() is only supposed to be called for non FSM fields
        field_mock.save = Mock()
        fsm_field_mock.save = Mock()

        # Call the method with FSMField and non-FSMField
        self.resource.import_field(fsm_field_mock, obj, data=data_mock, is_m2m=False)
        self.resource.import_field(field_mock, obj, data=data_mock, is_m2m=False)

        # Assert that field.save() in super().import_field() is called only for non-FSMField
        field_mock.save.assert_called_once()
        fsm_field_mock.save.assert_not_called()


class TestDomainAdmin(MockEppLib, WebTest):
    # csrf checks do not work with WebTest.
    # We disable them here. TODO for another ticket.
    csrf_checks = False

    def setUp(self):
        self.site = AdminSite()
        self.admin = DomainAdmin(model=Domain, admin_site=self.site)
        self.client = Client(HTTP_HOST="localhost:8080")
        self.superuser = create_superuser()
        self.staffuser = create_user()
        self.factory = RequestFactory()
        self.app.set_user(self.superuser.username)
        self.client.force_login(self.superuser)

        # Add domain data
        self.ready_domain, _ = Domain.objects.get_or_create(name="fakeready.gov", state=Domain.State.READY)
        self.unknown_domain, _ = Domain.objects.get_or_create(name="fakeunknown.gov", state=Domain.State.UNKNOWN)
        self.dns_domain, _ = Domain.objects.get_or_create(name="fakedns.gov", state=Domain.State.DNS_NEEDED)
        self.hold_domain, _ = Domain.objects.get_or_create(name="fakehold.gov", state=Domain.State.ON_HOLD)
        self.deleted_domain, _ = Domain.objects.get_or_create(name="fakedeleted.gov", state=Domain.State.DELETED)

        # Contains some test tools
        self.test_helper = GenericTestHelper(
            factory=self.factory,
            user=self.superuser,
            admin=self.admin,
            url=reverse("admin:registrar_domain_changelist"),
            model=Domain,
            client=self.client,
        )
        super().setUp()

    @less_console_noise_decorator
    def test_staff_can_see_cisa_region_federal(self):
        """Tests if staff can see CISA Region: N/A"""

        # Create a fake domain request
        _domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)
        _domain_request.approve()

        domain = _domain_request.approved_domain
        p = "userpass"
        self.client.login(username="staffuser", password=p)
        response = self.client.get(
            "/admin/registrar/domain/{}/change/".format(domain.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)

        # Test if the page has the right CISA region
        expected_html = '<div class="flex-container margin-top-2"><span>CISA region: N/A</span></div>'
        # Remove whitespace from expected_html
        expected_html = "".join(expected_html.split())

        # Remove whitespace from response content
        response_content = "".join(response.content.decode().split())

        # Check if response contains expected_html
        self.assertIn(expected_html, response_content)

    @less_console_noise_decorator
    def test_staff_can_see_cisa_region_non_federal(self):
        """Tests if staff can see the correct CISA region"""

        # Create a fake domain request. State will be NY (2).
        _domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.IN_REVIEW, generic_org_type="interstate"
        )

        _domain_request.approve()

        domain = _domain_request.approved_domain

        p = "userpass"
        self.client.login(username="staffuser", password=p)
        response = self.client.get(
            "/admin/registrar/domain/{}/change/".format(domain.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)

        # Test if the page has the right CISA region
        expected_html = '<div class="flex-container margin-top-2"><span>CISA region: 2</span></div>'
        # Remove whitespace from expected_html
        expected_html = "".join(expected_html.split())

        # Remove whitespace from response content
        response_content = "".join(response.content.decode().split())

        # Check if response contains expected_html
        self.assertIn(expected_html, response_content)

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/domain/",
            follow=True,
        )

        # Make sure that the page is loaded correctly
        self.assertEqual(response.status_code, 200)

        # Test for a description snippet
        self.assertContains(response, "This table contains all approved domains in the .gov registrar.")
        self.assertContains(response, "Show more")

    @less_console_noise_decorator
    def test_contact_fields_on_domain_change_form_have_detail_table(self):
        """Tests if the contact fields in the inlined Domain information have the detail table
        which displays title, email, and phone"""

        # Create fake creator
        _creator = User.objects.create(
            username="MrMeoward",
            first_name="Meoward",
            last_name="Jones",
        )

        # Due to the relation between User <==> Contact,
        # the underlying contact has to be modified this way.
        _creator.contact.email = "meoward.jones@igorville.gov"
        _creator.contact.phone = "(555) 123 12345"
        _creator.contact.title = "Treat inspector"
        _creator.contact.save()

        # Create a fake domain request
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW, user=_creator)
        domain_request.approve()
        _domain_info = DomainInformation.objects.filter(domain=domain_request.approved_domain).get()
        domain = Domain.objects.filter(domain_info=_domain_info).get()

        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/domain/{}/change/".format(domain.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)

        # Check that the fields have the right values.
        # == Check for the creator == #

        # Check for the right title, email, and phone number in the response.
        # We only need to check for the end tag
        # (Otherwise this test will fail if we change classes, etc)
        self.assertContains(response, "Treat inspector")
        self.assertContains(response, "meoward.jones@igorville.gov")
        self.assertContains(response, "(555) 123 12345")

        # Check for the field itself
        self.assertContains(response, "Meoward Jones")

        # == Check for the submitter == #
        self.assertContains(response, "mayor@igorville.gov")

        self.assertContains(response, "Admin Tester")
        self.assertContains(response, "(555) 555 5556")
        self.assertContains(response, "Testy2 Tester2")

        # == Check for the authorizing_official == #
        self.assertContains(response, "testy@town.com")
        self.assertContains(response, "Chief Tester")
        self.assertContains(response, "(555) 555 5555")

        # Includes things like readonly fields
        self.assertContains(response, "Testy Tester")

        # == Test the other_employees field == #
        self.assertContains(response, "testy2@town.com")
        self.assertContains(response, "Another Tester")
        self.assertContains(response, "(555) 555 5557")

        # Test for the copy link
        self.assertContains(response, "usa-button__clipboard")

    @less_console_noise_decorator
    def test_helper_text(self):
        """
        Tests for the correct helper text on this page
        """

        # Create a ready domain with a preset expiration date
        domain, _ = Domain.objects.get_or_create(name="fake.gov", state=Domain.State.READY)

        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/domain/{}/change/".format(domain.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)

        # These should exist in the response
        expected_values = [
            ("expiration_date", "Date the domain expires in the registry"),
            ("first_ready_at", 'Date when this domain first moved into "ready" state; date will never change'),
            ("deleted_at", 'Will appear blank unless the domain is in "deleted" state'),
        ]
        self.test_helper.assert_response_contains_distinct_values(response, expected_values)

    @less_console_noise_decorator
    def test_helper_text_state(self):
        """
        Tests for the correct state helper text on this page
        """

        # We don't need to check for all text content, just a portion of it
        expected_unknown_domain_message = "The creator of the associated domain request has not logged in to"
        expected_dns_message = "Before this domain can be used, name server addresses need"
        expected_hold_message = "While on hold, this domain"
        expected_deleted_message = "This domain was permanently removed from the registry."
        expected_messages = [
            (self.ready_domain, "This domain has name servers and is ready for use."),
            (self.unknown_domain, expected_unknown_domain_message),
            (self.dns_domain, expected_dns_message),
            (self.hold_domain, expected_hold_message),
            (self.deleted_domain, expected_deleted_message),
        ]

        p = "adminpass"
        self.client.login(username="superuser", password=p)
        for domain, message in expected_messages:
            with self.subTest(domain_state=domain.state):
                response = self.client.get(
                    "/admin/registrar/domain/{}/change/".format(domain.id),
                )

                # Make sure the page loaded, and that we're on the right page
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, domain.name)

                # Check that the right help text exists
                self.assertContains(response, message)

    @patch("registrar.admin.DomainAdmin._get_current_date", return_value=date(2024, 1, 1))
    def test_extend_expiration_date_button(self, mock_date_today):
        """
        Tests if extend_expiration_date modal gives an accurate date
        """

        # Create a ready domain with a preset expiration date
        domain, _ = Domain.objects.get_or_create(name="fake.gov", state=Domain.State.READY)

        response = self.app.get(reverse("admin:registrar_domain_change", args=[domain.pk]))

        # Make sure the ex date is what we expect it to be
        domain_ex_date = Domain.objects.get(id=domain.id).expiration_date
        self.assertEqual(domain_ex_date, date(2023, 5, 25))

        # Make sure that the page is loading as expected
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)
        self.assertContains(response, "Extend expiration date")

        # Grab the form to submit
        form = response.forms["domain_form"]

        with patch("django.contrib.messages.add_message") as mock_add_message:
            # Submit the form
            response = form.submit("_extend_expiration_date")

            # Follow the response
            response = response.follow()

        # Assert that everything on the page looks correct
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)
        self.assertContains(response, "Extend expiration date")
        self.assertContains(response, "New expiration date: <b>May 25, 2025</b>")

        # Ensure the message we recieve is in line with what we expect
        expected_message = "Successfully extended the expiration date."
        expected_call = call(
            # The WGSI request doesn't need to be tested
            ANY,
            messages.INFO,
            expected_message,
            extra_tags="",
            fail_silently=False,
        )

        mock_add_message.assert_has_calls([expected_call], 1)

    @less_console_noise_decorator
    def test_analyst_can_see_inline_domain_information_in_domain_change_form(self):
        """Tests if an analyst can still see the inline domain information form"""

        # Create fake creator
        _creator = User.objects.create(
            username="MrMeoward",
            first_name="Meoward",
            last_name="Jones",
        )

        # Create a fake domain request
        _domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW, user=_creator)

        # Creates a Domain and DomainInformation object
        _domain_request.approve()

        domain_information = DomainInformation.objects.filter(domain_request=_domain_request).get()
        domain_information.organization_name = "MonkeySeeMonkeyDo"
        domain_information.save()

        # We use filter here rather than just domain_information.domain just to get the latest data.
        domain = Domain.objects.filter(domain_info=domain_information).get()

        p = "userpass"
        self.client.login(username="staffuser", password=p)
        response = self.client.get(
            "/admin/registrar/domain/{}/change/".format(domain.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)

        # Test for data. We only need to test one since its all interconnected.
        expected_organization_name = "MonkeySeeMonkeyDo"
        self.assertContains(response, expected_organization_name)

    @less_console_noise_decorator
    def test_admin_can_see_inline_domain_information_in_domain_change_form(self):
        """Tests if an admin can still see the inline domain information form"""
        # Create fake creator
        _creator = User.objects.create(
            username="MrMeoward",
            first_name="Meoward",
            last_name="Jones",
        )

        # Create a fake domain request
        _domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW, user=_creator)

        # Creates a Domain and DomainInformation object
        _domain_request.approve()

        domain_information = DomainInformation.objects.filter(domain_request=_domain_request).get()
        domain_information.organization_name = "MonkeySeeMonkeyDo"
        domain_information.save()

        # We use filter here rather than just domain_information.domain just to get the latest data.
        domain = Domain.objects.filter(domain_info=domain_information).get()

        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/domain/{}/change/".format(domain.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)

        # Test for data. We only need to test one since its all interconnected.
        expected_organization_name = "MonkeySeeMonkeyDo"
        self.assertContains(response, expected_organization_name)

    @patch("registrar.admin.DomainAdmin._get_current_date", return_value=date(2024, 1, 1))
    def test_extend_expiration_date_button_epp(self, mock_date_today):
        """
        Tests if extend_expiration_date button sends the right epp command
        """

        # Create a ready domain with a preset expiration date
        domain, _ = Domain.objects.get_or_create(name="fake.gov", state=Domain.State.READY)

        response = self.app.get(reverse("admin:registrar_domain_change", args=[domain.pk]))

        # Make sure that the page is loading as expected
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)
        self.assertContains(response, "Extend expiration date")

        # Grab the form to submit
        form = response.forms["domain_form"]

        with patch("django.contrib.messages.add_message") as mock_add_message:
            with patch("registrar.models.Domain.renew_domain") as renew_mock:
                # Submit the form
                response = form.submit("_extend_expiration_date")

                # Follow the response
                response = response.follow()

        # This value is based off of the current year - the expiration date.
        # We "freeze" time to 2024, so 2024 - 2023 will always result in an
        # "extension" of 2, as that will be one year of extension from that date.
        extension_length = 2

        # Assert that it is calling the function with the right extension length.
        # We only need to test the value that EPP sends, as we can assume the other
        # test cases cover the "renew" function.
        renew_mock.assert_has_calls([call(length=extension_length)], any_order=False)

        # We should not make duplicate calls
        self.assertEqual(renew_mock.call_count, 1)

        # Assert that everything on the page looks correct
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)
        self.assertContains(response, "Extend expiration date")

        # Ensure the message we recieve is in line with what we expect
        expected_message = "Successfully extended the expiration date."
        expected_call = call(
            # The WGSI request doesn't need to be tested
            ANY,
            messages.INFO,
            expected_message,
            extra_tags="",
            fail_silently=False,
        )
        mock_add_message.assert_has_calls([expected_call], 1)

    @patch("registrar.admin.DomainAdmin._get_current_date", return_value=date(2023, 1, 1))
    def test_extend_expiration_date_button_date_matches_epp(self, mock_date_today):
        """
        Tests if extend_expiration_date button sends the right epp command
        when the current year matches the expiration date
        """

        # Create a ready domain with a preset expiration date
        domain, _ = Domain.objects.get_or_create(name="fake.gov", state=Domain.State.READY)

        response = self.app.get(reverse("admin:registrar_domain_change", args=[domain.pk]))

        # Make sure that the page is loading as expected
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)
        self.assertContains(response, "Extend expiration date")

        # Grab the form to submit
        form = response.forms["domain_form"]

        with patch("django.contrib.messages.add_message") as mock_add_message:
            with patch("registrar.models.Domain.renew_domain") as renew_mock:
                # Submit the form
                response = form.submit("_extend_expiration_date")

                # Follow the response
                response = response.follow()

        extension_length = 1

        # Assert that it is calling the function with the right extension length.
        # We only need to test the value that EPP sends, as we can assume the other
        # test cases cover the "renew" function.
        renew_mock.assert_has_calls([call(length=extension_length)], any_order=False)

        # We should not make duplicate calls
        self.assertEqual(renew_mock.call_count, 1)

        # Assert that everything on the page looks correct
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)
        self.assertContains(response, "Extend expiration date")

        # Ensure the message we recieve is in line with what we expect
        expected_message = "Successfully extended the expiration date."
        expected_call = call(
            # The WGSI request doesn't need to be tested
            ANY,
            messages.INFO,
            expected_message,
            extra_tags="",
            fail_silently=False,
        )
        mock_add_message.assert_has_calls([expected_call], 1)

    def test_custom_delete_confirmation_page(self):
        """Tests if we override the delete confirmation page for custom content"""
        # Create a ready domain with a preset expiration date
        domain, _ = Domain.objects.get_or_create(name="fake.gov", state=Domain.State.READY)

        domain_change_page = self.app.get(reverse("admin:registrar_domain_change", args=[domain.pk]))

        self.assertContains(domain_change_page, "fake.gov")
        # click the "Manage" link
        confirmation_page = domain_change_page.click("Delete", index=0)

        content_slice = "When a domain is deleted:"
        self.assertContains(confirmation_page, content_slice)

    def test_custom_delete_confirmation_page_table(self):
        """Tests if we override the delete confirmation page for custom content on the table"""
        # Create a ready domain
        domain, _ = Domain.objects.get_or_create(name="fake.gov", state=Domain.State.READY)

        # Get the index. The post expects the index to be encoded as a string
        index = f"{domain.id}"

        # Simulate selecting a single record, then clicking "Delete selected domains"
        response = self.test_helper.get_table_delete_confirmation_page("0", index)

        # Check that our content exists
        content_slice = "When a domain is deleted:"
        self.assertContains(response, content_slice)

    def test_short_org_name_in_domains_list(self):
        """
        Make sure the short name is displaying in admin on the list page
        """
        with less_console_noise():
            self.client.force_login(self.superuser)
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)
            mock_client = MockSESClient()
            with boto3_mocking.clients.handler_for("sesv2", mock_client):
                domain_request.approve()

            response = self.client.get("/admin/registrar/domain/")
            # There are 4 template references to Federal (4) plus four references in the table
            # for our actual domain_request
            self.assertContains(response, "Federal", count=56)
            # This may be a bit more robust
            self.assertContains(response, '<td class="field-generic_org_type">Federal</td>', count=1)
            # Now let's make sure the long description does not exist
            self.assertNotContains(response, "Federal: an agency of the U.S. government")

    @skip("Why did this test stop working, and is is a good test")
    def test_place_and_remove_hold(self):
        domain = create_ready_domain()
        # get admin page and assert Place Hold button
        p = "userpass"
        self.client.login(username="staffuser", password=p)
        response = self.client.get(
            "/admin/registrar/domain/{}/change/".format(domain.pk),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)
        self.assertContains(response, "Place hold")
        self.assertNotContains(response, "Remove hold")

        # submit place_client_hold and assert Remove Hold button
        response = self.client.post(
            "/admin/registrar/domain/{}/change/".format(domain.pk),
            {"_place_client_hold": "Place hold", "name": domain.name},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)
        self.assertContains(response, "Remove hold")
        self.assertNotContains(response, "Place hold")

        # submit remove client hold and assert Place hold button
        response = self.client.post(
            "/admin/registrar/domain/{}/change/".format(domain.pk),
            {"_remove_client_hold": "Remove hold", "name": domain.name},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)
        self.assertContains(response, "Place hold")
        self.assertNotContains(response, "Remove hold")

    def test_deletion_is_successful(self):
        """
        Scenario: Domain deletion is unsuccessful
            When the domain is deleted
            Then a user-friendly success message is returned for displaying on the web
            And `state` is set to `DELETED`
        """
        with less_console_noise():
            domain = create_ready_domain()
            # Put in client hold
            domain.place_client_hold()
            p = "userpass"
            self.client.login(username="staffuser", password=p)
            # Ensure everything is displaying correctly
            response = self.client.get(
                "/admin/registrar/domain/{}/change/".format(domain.pk),
                follow=True,
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, domain.name)
            self.assertContains(response, "Remove from registry")

            # The contents of the modal should exist before and after the post.
            # Check for the header
            self.assertContains(response, "Are you sure you want to remove this domain from the registry?")

            # Check for some of its body
            self.assertContains(response, "When a domain is removed from the registry:")

            # Check for some of the button content
            self.assertContains(response, "Yes, remove from registry")

            # Test the info dialog
            request = self.factory.post(
                "/admin/registrar/domain/{}/change/".format(domain.pk),
                {"_delete_domain": "Remove from registry", "name": domain.name},
                follow=True,
            )
            request.user = self.client
            with patch("django.contrib.messages.add_message") as mock_add_message:
                self.admin.do_delete_domain(request, domain)
                mock_add_message.assert_called_once_with(
                    request,
                    messages.INFO,
                    "Domain city.gov has been deleted. Thanks!",
                    extra_tags="",
                    fail_silently=False,
                )

            # The modal should still exist
            self.assertContains(response, "Are you sure you want to remove this domain from the registry?")
            self.assertContains(response, "When a domain is removed from the registry:")
            self.assertContains(response, "Yes, remove from registry")

            self.assertEqual(domain.state, Domain.State.DELETED)

    def test_on_hold_is_successful_web_test(self):
        """
        Scenario: Domain on_hold is successful through webtest
        """
        with less_console_noise():
            domain = create_ready_domain()

            response = self.app.get(reverse("admin:registrar_domain_change", args=[domain.pk]))

            # Check the contents of the modal
            # Check for the header
            self.assertContains(response, "Are you sure you want to place this domain on hold?")

            # Check for some of its body
            self.assertContains(response, "When a domain is on hold:")

            # Check for some of the button content
            self.assertContains(response, "Yes, place hold")

            # Grab the form to submit
            form = response.forms["domain_form"]

            # Submit the form
            response = form.submit("_place_client_hold")

            # Follow the response
            response = response.follow()

            self.assertEqual(response.status_code, 200)
            self.assertContains(response, domain.name)
            self.assertContains(response, "Remove hold")

            # The modal should still exist
            # Check for the header
            self.assertContains(response, "Are you sure you want to place this domain on hold?")

            # Check for some of its body
            self.assertContains(response, "When a domain is on hold:")

            # Check for some of the button content
            self.assertContains(response, "Yes, place hold")

            # Web test has issues grabbing up to date data from the db, so we can test
            # the returned view instead
            self.assertContains(response, '<div class="readonly">On hold</div>')

    def test_deletion_ready_fsm_failure(self):
        """
        Scenario: Domain deletion is unsuccessful
            When an error is returned from epplibwrapper
            Then a user-friendly error message is returned for displaying on the web
            And `state` is not set to `DELETED`
        """
        with less_console_noise():
            domain = create_ready_domain()
            p = "userpass"
            self.client.login(username="staffuser", password=p)
            # Ensure everything is displaying correctly
            response = self.client.get(
                "/admin/registrar/domain/{}/change/".format(domain.pk),
                follow=True,
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, domain.name)
            self.assertContains(response, "Remove from registry")
            # Test the error
            request = self.factory.post(
                "/admin/registrar/domain/{}/change/".format(domain.pk),
                {"_delete_domain": "Remove from registry", "name": domain.name},
                follow=True,
            )
            request.user = self.client
            with patch("django.contrib.messages.add_message") as mock_add_message:
                self.admin.do_delete_domain(request, domain)
                mock_add_message.assert_called_once_with(
                    request,
                    messages.ERROR,
                    "Error deleting this Domain: "
                    "Can't switch from state 'ready' to 'deleted'"
                    ", must be either 'dns_needed' or 'on_hold'",
                    extra_tags="",
                    fail_silently=False,
                )

        self.assertEqual(domain.state, Domain.State.READY)

    def test_analyst_deletes_domain_idempotent(self):
        """
        Scenario: Analyst tries to delete an already deleted domain
            Given `state` is already `DELETED`
            When `domain.deletedInEpp()` is called
            Then `commands.DeleteDomain` is sent to the registry
            And Domain returns normally without an error dialog
        """
        with less_console_noise():
            domain = create_ready_domain()
            # Put in client hold
            domain.place_client_hold()
            p = "userpass"
            self.client.login(username="staffuser", password=p)
            # Ensure everything is displaying correctly
            response = self.client.get(
                "/admin/registrar/domain/{}/change/".format(domain.pk),
                follow=True,
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, domain.name)
            self.assertContains(response, "Remove from registry")
            # Test the info dialog
            request = self.factory.post(
                "/admin/registrar/domain/{}/change/".format(domain.pk),
                {"_delete_domain": "Remove from registry", "name": domain.name},
                follow=True,
            )
            request.user = self.client
            # Delete it once
            with patch("django.contrib.messages.add_message") as mock_add_message:
                self.admin.do_delete_domain(request, domain)
                mock_add_message.assert_called_once_with(
                    request,
                    messages.INFO,
                    "Domain city.gov has been deleted. Thanks!",
                    extra_tags="",
                    fail_silently=False,
                )

            self.assertEqual(domain.state, Domain.State.DELETED)
            # Try to delete it again
            # Test the info dialog
            request = self.factory.post(
                "/admin/registrar/domain/{}/change/".format(domain.pk),
                {"_delete_domain": "Remove from registry", "name": domain.name},
                follow=True,
            )
            request.user = self.client
            with patch("django.contrib.messages.add_message") as mock_add_message:
                self.admin.do_delete_domain(request, domain)
                mock_add_message.assert_called_once_with(
                    request,
                    messages.INFO,
                    "This domain is already deleted",
                    extra_tags="",
                    fail_silently=False,
                )
            self.assertEqual(domain.state, Domain.State.DELETED)

    @skip("Waiting on epp lib to implement")
    def test_place_and_remove_hold_epp(self):
        raise

    @override_settings(IS_PRODUCTION=True)
    def test_prod_only_shows_export(self):
        """Test that production environment only displays export"""
        with less_console_noise():
            response = self.client.get("/admin/registrar/domain/")
            self.assertContains(response, ">Export<")
            self.assertNotContains(response, ">Import<")

    def tearDown(self):
        super().tearDown()
        PublicContact.objects.all().delete()
        Host.objects.all().delete()
        Domain.objects.all().delete()
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        User.objects.all().delete()


class TestDomainRequestAdminForm(TestCase):
    def setUp(self):
        # Create a test domain request with an initial state of started
        self.domain_request = completed_domain_request()

    def test_form_choices(self):
        with less_console_noise():
            # Create a form instance with the test domain request
            form = DomainRequestAdminForm(instance=self.domain_request)

            # Verify that the form choices match the available transitions for started
            expected_choices = [("started", "Started"), ("submitted", "Submitted")]
            self.assertEqual(form.fields["status"].widget.choices, expected_choices)

    def test_form_no_rejection_reason(self):
        with less_console_noise():
            # Create a form instance with the test domain request
            form = DomainRequestAdminForm(instance=self.domain_request)

            form = DomainRequestAdminForm(
                instance=self.domain_request,
                data={
                    "status": DomainRequest.DomainRequestStatus.REJECTED,
                    "rejection_reason": None,
                },
            )
            self.assertFalse(form.is_valid())
            self.assertIn("rejection_reason", form.errors)

            rejection_reason = form.errors.get("rejection_reason")
            self.assertEqual(rejection_reason, ["A rejection reason is required."])

    def test_form_choices_when_no_instance(self):
        with less_console_noise():
            # Create a form instance without an instance
            form = DomainRequestAdminForm()

            # Verify that the form choices show all choices when no instance is provided;
            # this is necessary to show all choices when creating a new domain
            # request in django admin;
            # note that FSM ensures that no domain request exists with invalid status,
            # so don't need to test for invalid status
            self.assertEqual(
                form.fields["status"].widget.choices,
                DomainRequest._meta.get_field("status").choices,
            )

    def test_form_choices_when_ineligible(self):
        with less_console_noise():
            # Create a form instance with a domain request with ineligible status
            ineligible_domain_request = DomainRequest(status="ineligible")

            # Attempt to create a form with the ineligible domain request
            # The form should not raise an error, but choices should be the
            # full list of possible choices
            form = DomainRequestAdminForm(instance=ineligible_domain_request)

            self.assertEqual(
                form.fields["status"].widget.choices,
                DomainRequest._meta.get_field("status").choices,
            )


@boto3_mocking.patching
class TestDomainRequestAdmin(MockEppLib):
    def setUp(self):
        super().setUp()
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.admin = DomainRequestAdmin(model=DomainRequest, admin_site=self.site)
        self.superuser = create_superuser()
        self.staffuser = create_user()
        self.client = Client(HTTP_HOST="localhost:8080")
        self.test_helper = GenericTestHelper(
            factory=self.factory,
            user=self.superuser,
            admin=self.admin,
            url="/admin/registrar/domainrequest/",
            model=DomainRequest,
        )
        self.mock_client = MockSESClient()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/domainrequest/",
            follow=True,
        )

        # Make sure that the page is loaded correctly
        self.assertEqual(response.status_code, 200)

        # Test for a description snippet
        self.assertContains(response, "This table contains all domain requests")
        self.assertContains(response, "Show more")

    @less_console_noise_decorator
    def test_helper_text(self):
        """
        Tests for the correct helper text on this page
        """

        # Create a fake domain request and domain
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/domainrequest/{}/change/".format(domain_request.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain_request.requested_domain.name)

        # These should exist in the response
        expected_values = [
            ("creator", "Person who submitted the domain request; will not receive email updates"),
            (
                "submitter",
                'Person listed under "your contact information" in the request form; will receive email updates',
            ),
            ("approved_domain", "Domain associated with this request; will be blank until request is approved"),
            ("no_other_contacts_rationale", "Required if creator does not list other employees"),
            ("alternative_domains", "Other domain names the creator provided for consideration"),
            ("no_other_contacts_rationale", "Required if creator does not list other employees"),
            ("Urbanization", "Required for Puerto Rico only"),
        ]
        self.test_helper.assert_response_contains_distinct_values(response, expected_values)

    @less_console_noise_decorator
    def test_status_logs(self):
        """
        Tests that the status changes are shown in a table on the domain request change form,
        accurately and in chronological order.
        """

        def assert_status_count(normalized_content, status, count):
            """Helper function to assert the count of a status in the HTML content."""
            self.assertEqual(normalized_content.count(f"<td> {status} </td>"), count)

        def assert_status_order(normalized_content, statuses):
            """Helper function to assert the order of statuses in the HTML content."""
            start_index = 0
            for status in statuses:
                index = normalized_content.find(f"<td> {status} </td>", start_index)
                self.assertNotEqual(index, -1, f"Status '{status}' not found in the expected order.")
                start_index = index + len(status)

        # Create a fake domain request and domain
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.STARTED)

        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/domainrequest/{}/change/".format(domain_request.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain_request.requested_domain.name)

        domain_request.submit()
        domain_request.save()

        domain_request.in_review()
        domain_request.save()

        domain_request.action_needed()
        domain_request.action_needed_reason = DomainRequest.ActionNeededReasons.ALREADY_HAS_DOMAINS
        domain_request.save()

        # Let's just change the action needed reason
        domain_request.action_needed_reason = DomainRequest.ActionNeededReasons.ELIGIBILITY_UNCLEAR
        domain_request.save()

        domain_request.reject()
        domain_request.rejection_reason = DomainRequest.RejectionReasons.DOMAIN_PURPOSE
        domain_request.save()

        domain_request.in_review()
        domain_request.save()

        response = self.client.get(
            "/admin/registrar/domainrequest/{}/change/".format(domain_request.pk),
            follow=True,
        )

        # Normalize the HTML response content
        normalized_content = " ".join(response.content.decode("utf-8").split())

        # Define the expected sequence of status changes
        expected_status_changes = [
            "In review",
            "Rejected - Purpose requirements not met",
            "Action needed - Unclear organization eligibility",
            "Action needed - Already has domains",
            "In review",
            "Submitted",
            "Started",
        ]

        assert_status_order(normalized_content, expected_status_changes)

        assert_status_count(normalized_content, "Started", 1)
        assert_status_count(normalized_content, "Submitted", 1)
        assert_status_count(normalized_content, "In review", 2)
        assert_status_count(normalized_content, "Action needed - Already has domains", 1)
        assert_status_count(normalized_content, "Action needed - Unclear organization eligibility", 1)
        assert_status_count(normalized_content, "Rejected - Purpose requirements not met", 1)

    def test_collaspe_toggle_button_markup(self):
        """
        Tests for the correct collapse toggle button markup
        """

        # Create a fake domain request and domain
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/domainrequest/{}/change/".format(domain_request.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain_request.requested_domain.name)
        self.test_helper.assertContains(response, "<span>Show details</span>")

    @less_console_noise_decorator
    def test_analyst_can_see_and_edit_alternative_domain(self):
        """Tests if an analyst can still see and edit the alternative domain field"""

        # Create fake creator
        _creator = User.objects.create(
            username="MrMeoward",
            first_name="Meoward",
            last_name="Jones",
        )

        # Create a fake domain request
        _domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW, user=_creator)

        fake_website = Website.objects.create(website="thisisatest.gov")
        _domain_request.alternative_domains.add(fake_website)
        _domain_request.save()

        p = "userpass"
        self.client.login(username="staffuser", password=p)
        response = self.client.get(
            "/admin/registrar/domainrequest/{}/change/".format(_domain_request.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, _domain_request.requested_domain.name)

        # Test if the page has the alternative domain
        self.assertContains(response, "thisisatest.gov")

        # Check that the page contains the url we expect
        expected_href = reverse("admin:registrar_website_change", args=[fake_website.id])
        self.assertContains(response, expected_href)

        # Navigate to the website to ensure that we can still edit it
        response = self.client.get(
            "/admin/registrar/website/{}/change/".format(fake_website.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "thisisatest.gov")

    @less_console_noise_decorator
    def test_analyst_can_see_and_edit_requested_domain(self):
        """Tests if an analyst can still see and edit the requested domain field"""

        # Create fake creator
        _creator = User.objects.create(
            username="MrMeoward",
            first_name="Meoward",
            last_name="Jones",
        )

        # Create a fake domain request
        _domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW, user=_creator)

        p = "userpass"
        self.client.login(username="staffuser", password=p)
        response = self.client.get(
            "/admin/registrar/domainrequest/{}/change/".format(_domain_request.pk),
            follow=True,
        )

        # Filter to get the latest from the DB (rather than direct assignment)
        requested_domain = DraftDomain.objects.filter(name=_domain_request.requested_domain.name).get()

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, requested_domain.name)

        # Check that the page contains the url we expect
        expected_href = reverse("admin:registrar_draftdomain_change", args=[requested_domain.id])
        self.assertContains(response, expected_href)

        # Navigate to the website to ensure that we can still edit it
        response = self.client.get(
            "/admin/registrar/draftdomain/{}/change/".format(requested_domain.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "city.gov")

    @less_console_noise_decorator
    def test_analyst_can_see_current_websites(self):
        """Tests if an analyst can still see current website field"""

        # Create fake creator
        _creator = User.objects.create(
            username="MrMeoward",
            first_name="Meoward",
            last_name="Jones",
        )

        # Create a fake domain request
        _domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW, user=_creator)

        fake_website = Website.objects.create(website="thisisatest.gov")
        _domain_request.current_websites.add(fake_website)
        _domain_request.save()

        p = "userpass"
        self.client.login(username="staffuser", password=p)
        response = self.client.get(
            "/admin/registrar/domainrequest/{}/change/".format(_domain_request.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, _domain_request.requested_domain.name)

        # Test if the page has the current website
        self.assertContains(response, "thisisatest.gov")

    def test_domain_sortable(self):
        """Tests if the DomainRequest sorts by domain correctly"""
        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            multiple_unalphabetical_domain_objects("domain_request")

            # Assert that our sort works correctly
            self.test_helper.assert_table_sorted("1", ("requested_domain__name",))

            # Assert that sorting in reverse works correctly
            self.test_helper.assert_table_sorted("-1", ("-requested_domain__name",))

    def test_submitter_sortable(self):
        """Tests if the DomainRequest sorts by submitter correctly"""
        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            multiple_unalphabetical_domain_objects("domain_request")

            additional_domain_request = generic_domain_object("domain_request", "Xylophone")
            new_user = User.objects.filter(username=additional_domain_request.investigator.username).get()
            new_user.first_name = "Xylophonic"
            new_user.save()

            # Assert that our sort works correctly
            self.test_helper.assert_table_sorted(
                "11",
                (
                    "submitter__first_name",
                    "submitter__last_name",
                ),
            )

            # Assert that sorting in reverse works correctly
            self.test_helper.assert_table_sorted(
                "-11",
                (
                    "-submitter__first_name",
                    "-submitter__last_name",
                ),
            )

    def test_investigator_sortable(self):
        """Tests if the DomainRequest sorts by investigator correctly"""
        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            multiple_unalphabetical_domain_objects("domain_request")
            additional_domain_request = generic_domain_object("domain_request", "Xylophone")
            new_user = User.objects.filter(username=additional_domain_request.investigator.username).get()
            new_user.first_name = "Xylophonic"
            new_user.save()

            # Assert that our sort works correctly
            self.test_helper.assert_table_sorted(
                "12",
                (
                    "investigator__first_name",
                    "investigator__last_name",
                ),
            )

            # Assert that sorting in reverse works correctly
            self.test_helper.assert_table_sorted(
                "-12",
                (
                    "-investigator__first_name",
                    "-investigator__last_name",
                ),
            )

    @less_console_noise_decorator
    def test_default_sorting_in_domain_requests_list(self):
        """
        Make sure the default sortin in on the domain requests list page is reverse submission_date
        then alphabetical requested_domain
        """

        # Create domain requests with different names
        domain_requests = [
            completed_domain_request(status=DomainRequest.DomainRequestStatus.SUBMITTED, name=name)
            for name in ["ccc.gov", "bbb.gov", "eee.gov", "aaa.gov", "zzz.gov", "ddd.gov"]
        ]

        domain_requests[0].submission_date = timezone.make_aware(datetime(2024, 10, 16))
        domain_requests[1].submission_date = timezone.make_aware(datetime(2001, 10, 16))
        domain_requests[2].submission_date = timezone.make_aware(datetime(1980, 10, 16))
        domain_requests[3].submission_date = timezone.make_aware(datetime(1998, 10, 16))
        domain_requests[4].submission_date = timezone.make_aware(datetime(2013, 10, 16))
        domain_requests[5].submission_date = timezone.make_aware(datetime(1980, 10, 16))

        # Save the modified domain requests to update their attributes in the database
        for domain_request in domain_requests:
            domain_request.save()

        # Refresh domain request objects from the database to reflect the changes
        domain_requests = [DomainRequest.objects.get(pk=domain_request.pk) for domain_request in domain_requests]

        # Login as superuser and retrieve the domain request list page
        self.client.force_login(self.superuser)
        response = self.client.get("/admin/registrar/domainrequest/")

        # Check that the response is successful
        self.assertEqual(response.status_code, 200)

        # Extract the domain names from the response content using regex
        domain_names_match = re.findall(r"(\w+\.gov)</a>", response.content.decode("utf-8"))

        logger.info(f"domain_names_match {domain_names_match}")

        # Verify that domain names are found
        self.assertTrue(domain_names_match)

        # Extract the domain names
        domain_names = [match for match in domain_names_match]

        # Verify that the domain names are displayed in the expected order
        expected_order = [
            "ccc.gov",
            "zzz.gov",
            "bbb.gov",
            "aaa.gov",
            "ddd.gov",
            "eee.gov",
        ]

        # Remove duplicates
        # Remove duplicates from domain_names list while preserving order
        unique_domain_names = []
        for domain_name in domain_names:
            if domain_name not in unique_domain_names:
                unique_domain_names.append(domain_name)

        self.assertEqual(unique_domain_names, expected_order)

    def test_short_org_name_in_domain_requests_list(self):
        """
        Make sure the short name is displaying in admin on the list page
        """
        with less_console_noise():
            self.client.force_login(self.superuser)
            completed_domain_request()
            response = self.client.get("/admin/registrar/domainrequest/?generic_org_type__exact=federal")
            # There are 2 template references to Federal (4) and two in the results data
            # of the request
            self.assertContains(response, "Federal", count=52)
            # This may be a bit more robust
            self.assertContains(response, '<td class="field-generic_org_type">Federal</td>', count=1)
            # Now let's make sure the long description does not exist
            self.assertNotContains(response, "Federal: an agency of the U.S. government")

    def test_default_status_in_domain_requests_list(self):
        """
        Make sure the default status in admin is selected on the domain requests list page
        """
        with less_console_noise():
            self.client.force_login(self.superuser)
            completed_domain_request()
            response = self.client.get("/admin/registrar/domainrequest/")
            # The results are filtered by "status in [submitted,in review,action needed]"
            self.assertContains(response, "status in [submitted,in review,action needed]", count=1)

    @less_console_noise_decorator
    def transition_state_and_send_email(self, domain_request, status, rejection_reason=None, action_needed_reason=None):
        """Helper method for the email test cases."""

        with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
            # Create a mock request
            request = self.factory.post("/admin/registrar/domainrequest/{}/change/".format(domain_request.pk))

            # Modify the domain request's properties
            domain_request.status = status

            if rejection_reason:
                domain_request.rejection_reason = rejection_reason

            if action_needed_reason:
                domain_request.action_needed_reason = action_needed_reason

            # Use the model admin's save_model method
            self.admin.save_model(request, domain_request, form=None, change=True)

    def assert_email_is_accurate(
        self, expected_string, email_index, email_address, test_that_no_bcc=False, bcc_email_address=""
    ):
        """Helper method for the email test cases.
        email_index is the index of the email in mock_client."""

        with less_console_noise():
            # Access the arguments passed to send_email
            call_args = self.mock_client.EMAILS_SENT
            kwargs = call_args[email_index]["kwargs"]

            # Retrieve the email details from the arguments
            from_email = kwargs.get("FromEmailAddress")
            to_email = kwargs["Destination"]["ToAddresses"][0]
            email_content = kwargs["Content"]
            email_body = email_content["Simple"]["Body"]["Text"]["Data"]

            # Assert or perform other checks on the email details
            self.assertEqual(from_email, settings.DEFAULT_FROM_EMAIL)
            self.assertEqual(to_email, email_address)
            self.assertIn(expected_string, email_body)

        if test_that_no_bcc:
            _ = ""
            with self.assertRaises(KeyError):
                with less_console_noise():
                    _ = kwargs["Destination"]["BccAddresses"][0]
            self.assertEqual(_, "")

        if bcc_email_address:
            bcc_email = kwargs["Destination"]["BccAddresses"][0]
            self.assertEqual(bcc_email, bcc_email_address)

    @override_settings(IS_PRODUCTION=True)
    def test_action_needed_sends_reason_email_prod_bcc(self):
        """When an action needed reason is set, an email is sent out and help@get.gov
        is BCC'd in production"""
        # Ensure there is no user with this email
        EMAIL = "mayor@igorville.gov"
        BCC_EMAIL = settings.DEFAULT_FROM_EMAIL
        User.objects.filter(email=EMAIL).delete()
        in_review = DomainRequest.DomainRequestStatus.IN_REVIEW
        action_needed = DomainRequest.DomainRequestStatus.ACTION_NEEDED

        # Create a sample domain request
        domain_request = completed_domain_request(status=in_review)

        # Test the email sent out for already_has_domains
        already_has_domains = DomainRequest.ActionNeededReasons.ALREADY_HAS_DOMAINS
        self.transition_state_and_send_email(domain_request, action_needed, action_needed_reason=already_has_domains)
        self.assert_email_is_accurate("ORGANIZATION ALREADY HAS A .GOV DOMAIN", 0, EMAIL, bcc_email_address=BCC_EMAIL)
        self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

        # Test the email sent out for bad_name
        bad_name = DomainRequest.ActionNeededReasons.BAD_NAME
        self.transition_state_and_send_email(domain_request, action_needed, action_needed_reason=bad_name)
        self.assert_email_is_accurate(
            "DOMAIN NAME DOES NOT MEET .GOV REQUIREMENTS", 1, EMAIL, bcc_email_address=BCC_EMAIL
        )
        self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

        # Test the email sent out for eligibility_unclear
        eligibility_unclear = DomainRequest.ActionNeededReasons.ELIGIBILITY_UNCLEAR
        self.transition_state_and_send_email(domain_request, action_needed, action_needed_reason=eligibility_unclear)
        self.assert_email_is_accurate(
            "ORGANIZATION MAY NOT MEET ELIGIBILITY REQUIREMENTS", 2, EMAIL, bcc_email_address=BCC_EMAIL
        )
        self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

        # Test the email sent out for questionable_ao
        questionable_ao = DomainRequest.ActionNeededReasons.QUESTIONABLE_AUTHORIZING_OFFICIAL
        self.transition_state_and_send_email(domain_request, action_needed, action_needed_reason=questionable_ao)
        self.assert_email_is_accurate(
            "AUTHORIZING OFFICIAL DOES NOT MEET ELIGIBILITY REQUIREMENTS", 3, EMAIL, bcc_email_address=BCC_EMAIL
        )
        self.assertEqual(len(self.mock_client.EMAILS_SENT), 4)

        # Assert that no other emails are sent on OTHER
        other = DomainRequest.ActionNeededReasons.OTHER
        self.transition_state_and_send_email(domain_request, action_needed, action_needed_reason=other)

        # Should be unchanged from before
        self.assertEqual(len(self.mock_client.EMAILS_SENT), 4)

    def test_save_model_sends_submitted_email(self):
        """When transitioning to submitted from started or withdrawn on a domain request,
        an email is sent out.

        When transitioning to submitted from dns needed or in review on a domain request,
        no email is sent out.

        Also test that the default email set in settings is NOT BCCd on non-prod whenever
        an email does go out."""

        with less_console_noise():
            # Ensure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample domain request
            domain_request = completed_domain_request()

            # Test Submitted Status from started
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.SUBMITTED)
            self.assert_email_is_accurate("We received your .gov domain request.", 0, EMAIL, True)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

            # Test Withdrawn Status
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.WITHDRAWN)
            self.assert_email_is_accurate(
                "Your .gov domain request has been withdrawn and will not be reviewed by our team.", 1, EMAIL, True
            )
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

            # Test Submitted Status Again (from withdrawn)
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.SUBMITTED)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

            # Move it to IN_REVIEW
            other = DomainRequest.ActionNeededReasons.OTHER
            in_review = DomainRequest.DomainRequestStatus.IN_REVIEW
            self.transition_state_and_send_email(domain_request, in_review, action_needed_reason=other)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

            # Test Submitted Status Again from in IN_REVIEW, no new email should be sent
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.SUBMITTED)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

            # Move it to IN_REVIEW
            self.transition_state_and_send_email(domain_request, in_review, action_needed_reason=other)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

            # Move it to ACTION_NEEDED
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.ACTION_NEEDED)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

            # Test Submitted Status Again from in ACTION_NEEDED, no new email should be sent
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.SUBMITTED)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

    @override_settings(IS_PRODUCTION=True)
    def test_save_model_sends_submitted_email_with_bcc_on_prod(self):
        """When transitioning to submitted from started or withdrawn on a domain request,
        an email is sent out.

        When transitioning to submitted from dns needed or in review on a domain request,
        no email is sent out.

        Also test that the default email set in settings IS BCCd on prod whenever
        an email does go out."""

        with less_console_noise():
            # Ensure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            BCC_EMAIL = settings.DEFAULT_FROM_EMAIL

            # Create a sample domain request
            domain_request = completed_domain_request()

            # Test Submitted Status from started
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.SUBMITTED)
            self.assert_email_is_accurate("We received your .gov domain request.", 0, EMAIL, False, BCC_EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

            # Test Withdrawn Status
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.WITHDRAWN)
            self.assert_email_is_accurate(
                "Your .gov domain request has been withdrawn and will not be reviewed by our team.", 1, EMAIL
            )
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

            # Test Submitted Status Again (from withdrawn)
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.SUBMITTED)
            self.assert_email_is_accurate("We received your .gov domain request.", 0, EMAIL, False, BCC_EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

            # Move it to IN_REVIEW
            other = domain_request.ActionNeededReasons.OTHER
            in_review = DomainRequest.DomainRequestStatus.IN_REVIEW
            self.transition_state_and_send_email(domain_request, in_review, action_needed_reason=other)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

            # Test Submitted Status Again from in IN_REVIEW, no new email should be sent
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.SUBMITTED)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

            # Move it to IN_REVIEW
            self.transition_state_and_send_email(domain_request, in_review, action_needed_reason=other)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

            # Move it to ACTION_NEEDED
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.ACTION_NEEDED)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

            # Test Submitted Status Again from in ACTION_NEEDED, no new email should be sent
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.SUBMITTED)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

    def test_save_model_sends_approved_email(self):
        """When transitioning to approved on a domain request,
        an email is sent out every time."""

        with less_console_noise():
            # Ensure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample domain request
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            # Test Submitted Status
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.APPROVED)
            self.assert_email_is_accurate("Congratulations! Your .gov domain request has been approved.", 0, EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

            # Test Withdrawn Status
            self.transition_state_and_send_email(
                domain_request,
                DomainRequest.DomainRequestStatus.REJECTED,
                DomainRequest.RejectionReasons.DOMAIN_PURPOSE,
            )
            self.assert_email_is_accurate("Your .gov domain request has been rejected.", 1, EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

            # Test Submitted Status Again (No new email should be sent)
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.APPROVED)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

    def test_save_model_sends_rejected_email_purpose_not_met(self):
        """When transitioning to rejected on a domain request, an email is sent
        explaining why when the reason is domain purpose."""

        with less_console_noise():
            # Ensure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample domain request
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            # Reject for reason DOMAIN_PURPOSE and test email
            self.transition_state_and_send_email(
                domain_request,
                DomainRequest.DomainRequestStatus.REJECTED,
                DomainRequest.RejectionReasons.DOMAIN_PURPOSE,
            )
            self.assert_email_is_accurate(
                "Your domain request was rejected because the purpose you provided did not meet our \nrequirements.",
                0,
                EMAIL,
            )
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

            # Approve
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.APPROVED)
            self.assert_email_is_accurate("Congratulations! Your .gov domain request has been approved.", 1, EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

    def test_save_model_sends_rejected_email_requestor(self):
        """When transitioning to rejected on a domain request, an email is sent
        explaining why when the reason is requestor."""

        with less_console_noise():
            # Ensure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample domain request
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            # Reject for reason REQUESTOR and test email including dynamic organization name
            self.transition_state_and_send_email(
                domain_request, DomainRequest.DomainRequestStatus.REJECTED, DomainRequest.RejectionReasons.REQUESTOR
            )
            self.assert_email_is_accurate(
                "Your domain request was rejected because we don’t believe you’re eligible to request a \n.gov "
                "domain on behalf of Testorg",
                0,
                EMAIL,
            )
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

            # Approve
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.APPROVED)
            self.assert_email_is_accurate("Congratulations! Your .gov domain request has been approved.", 1, EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

    def test_save_model_sends_rejected_email_org_has_domain(self):
        """When transitioning to rejected on a domain request, an email is sent
        explaining why when the reason is second domain."""

        with less_console_noise():
            # Ensure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample domain request
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            # Reject for reason SECOND_DOMAIN_REASONING and test email including dynamic organization name
            self.transition_state_and_send_email(
                domain_request,
                DomainRequest.DomainRequestStatus.REJECTED,
                DomainRequest.RejectionReasons.SECOND_DOMAIN_REASONING,
            )
            self.assert_email_is_accurate(
                "Your domain request was rejected because Testorg has a .gov domain.", 0, EMAIL
            )
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

            # Approve
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.APPROVED)
            self.assert_email_is_accurate("Congratulations! Your .gov domain request has been approved.", 1, EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

    def test_save_model_sends_rejected_email_contacts_or_org_legitimacy(self):
        """When transitioning to rejected on a domain request, an email is sent
        explaining why when the reason is contacts or org legitimacy."""

        with less_console_noise():
            # Ensure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample domain request
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            # Reject for reason CONTACTS_OR_ORGANIZATION_LEGITIMACY and test email including dynamic organization name
            self.transition_state_and_send_email(
                domain_request,
                DomainRequest.DomainRequestStatus.REJECTED,
                DomainRequest.RejectionReasons.CONTACTS_OR_ORGANIZATION_LEGITIMACY,
            )
            self.assert_email_is_accurate(
                "Your domain request was rejected because we could not verify the organizational \n"
                "contacts you provided. If you have questions or comments, reply to this email.",
                0,
                EMAIL,
            )
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

            # Approve
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.APPROVED)
            self.assert_email_is_accurate("Congratulations! Your .gov domain request has been approved.", 1, EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

    def test_save_model_sends_rejected_email_org_eligibility(self):
        """When transitioning to rejected on a domain request, an email is sent
        explaining why when the reason is org eligibility."""

        with less_console_noise():
            # Ensure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample domain request
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            # Reject for reason ORGANIZATION_ELIGIBILITY and test email including dynamic organization name
            self.transition_state_and_send_email(
                domain_request,
                DomainRequest.DomainRequestStatus.REJECTED,
                DomainRequest.RejectionReasons.ORGANIZATION_ELIGIBILITY,
            )
            self.assert_email_is_accurate(
                "Your domain request was rejected because we determined that Testorg is not \neligible for "
                "a .gov domain.",
                0,
                EMAIL,
            )
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

            # Approve
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.APPROVED)
            self.assert_email_is_accurate("Congratulations! Your .gov domain request has been approved.", 1, EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

    def test_save_model_sends_rejected_email_naming(self):
        """When transitioning to rejected on a domain request, an email is sent
        explaining why when the reason is naming."""

        with less_console_noise():
            # Ensure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample domain request
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            # Reject for reason NAMING_REQUIREMENTS and test email including dynamic organization name
            self.transition_state_and_send_email(
                domain_request,
                DomainRequest.DomainRequestStatus.REJECTED,
                DomainRequest.RejectionReasons.NAMING_REQUIREMENTS,
            )
            self.assert_email_is_accurate(
                "Your domain request was rejected because it does not meet our naming requirements.", 0, EMAIL
            )
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

            # Approve
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.APPROVED)
            self.assert_email_is_accurate("Congratulations! Your .gov domain request has been approved.", 1, EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

    def test_save_model_sends_rejected_email_other(self):
        """When transitioning to rejected on a domain request, an email is sent
        explaining why when the reason is other."""

        with less_console_noise():
            # Ensure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample domain request
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            # Reject for reason NAMING_REQUIREMENTS and test email including dynamic organization name
            self.transition_state_and_send_email(
                domain_request,
                DomainRequest.DomainRequestStatus.REJECTED,
                DomainRequest.RejectionReasons.OTHER,
            )
            self.assert_email_is_accurate("Choosing a .gov domain name", 0, EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

            # Approve
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.APPROVED)
            self.assert_email_is_accurate("Congratulations! Your .gov domain request has been approved.", 1, EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

    def test_transition_to_rejected_without_rejection_reason_does_trigger_error(self):
        """
        When transitioning to rejected without a rejection reason, admin throws a user friendly message.

        The transition fails.
        """

        with less_console_noise():
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.APPROVED)

            # Create a request object with a superuser
            request = self.factory.post("/admin/registrar/domainrequest/{}/change/".format(domain_request.pk))
            request.user = self.superuser

            with ExitStack() as stack:
                stack.enter_context(patch.object(messages, "error"))
                domain_request.status = DomainRequest.DomainRequestStatus.REJECTED

                self.admin.save_model(request, domain_request, None, True)

                messages.error.assert_called_once_with(
                    request,
                    "A rejection reason is required.",
                )

            domain_request.refresh_from_db()
            self.assertEqual(domain_request.status, DomainRequest.DomainRequestStatus.APPROVED)

    def test_transition_to_rejected_with_rejection_reason_does_not_trigger_error(self):
        """
        When transitioning to rejected with a rejection reason, admin does not throw an error alert.

        The transition is successful.
        """

        with less_console_noise():
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.APPROVED)

            # Create a request object with a superuser
            request = self.factory.post("/admin/registrar/domainrequest/{}/change/".format(domain_request.pk))
            request.user = self.superuser

            with ExitStack() as stack:
                stack.enter_context(patch.object(messages, "error"))
                domain_request.status = DomainRequest.DomainRequestStatus.REJECTED
                domain_request.rejection_reason = DomainRequest.RejectionReasons.CONTACTS_OR_ORGANIZATION_LEGITIMACY

                self.admin.save_model(request, domain_request, None, True)

                messages.error.assert_not_called()

            domain_request.refresh_from_db()
            self.assertEqual(domain_request.status, DomainRequest.DomainRequestStatus.REJECTED)

    def test_save_model_sends_withdrawn_email(self):
        """When transitioning to withdrawn on a domain request,
        an email is sent out every time."""

        with less_console_noise():
            # Ensure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample domain request
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            # Test Submitted Status
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.WITHDRAWN)
            self.assert_email_is_accurate(
                "Your .gov domain request has been withdrawn and will not be reviewed by our team.", 0, EMAIL
            )
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 1)

            # Test Withdrawn Status
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.SUBMITTED)
            self.assert_email_is_accurate("We received your .gov domain request.", 1, EMAIL)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 2)

            # Test Submitted Status Again (No new email should be sent)
            self.transition_state_and_send_email(domain_request, DomainRequest.DomainRequestStatus.WITHDRAWN)
            self.assertEqual(len(self.mock_client.EMAILS_SENT), 3)

    def test_save_model_sets_approved_domain(self):
        with less_console_noise():
            # make sure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample domain request
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            # Create a mock request
            request = self.factory.post("/admin/registrar/domainrequest/{}/change/".format(domain_request.pk))

            with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
                # Modify the domain request's property
                domain_request.status = DomainRequest.DomainRequestStatus.APPROVED

                # Use the model admin's save_model method
                self.admin.save_model(request, domain_request, form=None, change=True)

            # Test that approved domain exists and equals requested domain
            self.assertEqual(domain_request.requested_domain.name, domain_request.approved_domain.name)

    @less_console_noise_decorator
    def test_sticky_submit_row(self):
        """Test that the change_form template contains strings indicative of the customization
        of the sticky submit bar.

        Also test that it does NOT contain a CSS class meant for analysts only when logged in as superuser."""

        # make sure there is no user with this email
        EMAIL = "mayor@igorville.gov"
        User.objects.filter(email=EMAIL).delete()
        self.client.force_login(self.superuser)

        # Create a sample domain request
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

        # Create a mock request
        request = self.client.post("/admin/registrar/domainrequest/{}/change/".format(domain_request.pk))

        # Since we're using client to mock the request, we can only test against
        # non-interpolated values
        expected_content = "Requested domain:"
        expected_content2 = '<span class="scroll-indicator"></span>'
        expected_content3 = '<div class="submit-row-wrapper">'
        not_expected_content = "submit-row-wrapper--analyst-view>"
        self.assertContains(request, expected_content)
        self.assertContains(request, expected_content2)
        self.assertContains(request, expected_content3)
        self.assertNotContains(request, not_expected_content)

    @less_console_noise_decorator
    def test_sticky_submit_row_has_extra_class_for_analysts(self):
        """Test that the change_form template contains strings indicative of the customization
        of the sticky submit bar.

        Also test that it DOES contain a CSS class meant for analysts only when logged in as analyst."""

        # make sure there is no user with this email
        EMAIL = "mayor@igorville.gov"
        User.objects.filter(email=EMAIL).delete()
        self.client.force_login(self.staffuser)

        # Create a sample domain request
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

        # Create a mock request
        request = self.client.post("/admin/registrar/domainrequest/{}/change/".format(domain_request.pk))

        # Since we're using client to mock the request, we can only test against
        # non-interpolated values
        expected_content = "Requested domain:"
        expected_content2 = '<span class="scroll-indicator"></span>'
        expected_content3 = '<div class="submit-row-wrapper submit-row-wrapper--analyst-view">'
        self.assertContains(request, expected_content)
        self.assertContains(request, expected_content2)
        self.assertContains(request, expected_content3)

    def test_other_contacts_has_readonly_link(self):
        """Tests if the readonly other_contacts field has links"""

        # Create a fake domain request
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

        # Get the other contact
        other_contact = domain_request.other_contacts.all().first()

        p = "userpass"
        self.client.login(username="staffuser", password=p)
        response = self.client.get(
            "/admin/registrar/domainrequest/{}/change/".format(domain_request.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain_request.requested_domain.name)

        # Check that the page contains the url we expect
        expected_href = reverse("admin:registrar_contact_change", args=[other_contact.id])
        self.assertContains(response, expected_href)

        # Check that the page contains the link we expect.
        # Since the url is dynamic (populated by JS), we can test for its existence
        # by checking for the end tag.
        expected_url = "Testy Tester</a>"
        self.assertContains(response, expected_url)

    @less_console_noise_decorator
    def test_other_websites_has_readonly_link(self):
        """Tests if the readonly other_websites field has links"""

        # Create a fake domain request
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

        p = "userpass"
        self.client.login(username="staffuser", password=p)
        response = self.client.get(
            "/admin/registrar/domainrequest/{}/change/".format(domain_request.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain_request.requested_domain.name)

        # Check that the page contains the link we expect.
        expected_url = '<a href="city.com" target="_blank" class="padding-top-1 current-website__1">city.com</a>'
        self.assertContains(response, expected_url)

    @less_console_noise_decorator
    def test_contact_fields_have_detail_table(self):
        """Tests if the contact fields have the detail table which displays title, email, and phone"""

        # Create fake creator
        _creator = User.objects.create(
            username="MrMeoward",
            first_name="Meoward",
            last_name="Jones",
        )

        # Due to the relation between User <==> Contact,
        # the underlying contact has to be modified this way.
        _creator.contact.email = "meoward.jones@igorville.gov"
        _creator.contact.phone = "(555) 123 12345"
        _creator.contact.title = "Treat inspector"
        _creator.contact.save()

        # Create a fake domain request
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW, user=_creator)

        p = "userpass"
        self.client.login(username="staffuser", password=p)
        response = self.client.get(
            "/admin/registrar/domainrequest/{}/change/".format(domain_request.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain_request.requested_domain.name)

        # == Check for the creator == #

        # Check for the right title, email, and phone number in the response.
        expected_creator_fields = [
            # Field, expected value
            ("title", "Treat inspector"),
            ("email", "meoward.jones@igorville.gov"),
            ("phone", "(555) 123 12345"),
        ]
        self.test_helper.assert_response_contains_distinct_values(response, expected_creator_fields)

        # Check for the field itself
        self.assertContains(response, "Meoward Jones")

        # == Check for the submitter == #
        self.assertContains(response, "mayor@igorville.gov", count=2)
        expected_submitter_fields = [
            # Field, expected value
            ("title", "Admin Tester"),
            ("phone", "(555) 555 5556"),
        ]
        self.test_helper.assert_response_contains_distinct_values(response, expected_submitter_fields)
        self.assertContains(response, "Testy2 Tester2")

        # == Check for the authorizing_official == #
        self.assertContains(response, "testy@town.com", count=2)
        expected_ao_fields = [
            # Field, expected value
            ("title", "Chief Tester"),
            ("phone", "(555) 555 5555"),
        ]
        self.test_helper.assert_response_contains_distinct_values(response, expected_ao_fields)

        self.assertContains(response, "Testy Tester", count=10)

        # == Test the other_employees field == #
        self.assertContains(response, "testy2@town.com", count=2)
        expected_other_employees_fields = [
            # Field, expected value
            ("title", "Another Tester"),
            ("phone", "(555) 555 5557"),
        ]
        self.test_helper.assert_response_contains_distinct_values(response, expected_other_employees_fields)

        # Test for the copy link
        self.assertContains(response, "usa-button__clipboard", count=4)

        # Test that Creator counts display properly
        self.assertNotContains(response, "Approved domains")
        self.assertContains(response, "Active requests")

    def test_save_model_sets_restricted_status_on_user(self):
        with less_console_noise():
            # make sure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample domain request
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            # Create a mock request
            request = self.factory.post(
                "/admin/registrar/domainrequest/{}/change/".format(domain_request.pk), follow=True
            )

            with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
                # Modify the domain request's property
                domain_request.status = DomainRequest.DomainRequestStatus.INELIGIBLE

                # Use the model admin's save_model method
                self.admin.save_model(request, domain_request, form=None, change=True)

            # Test that approved domain exists and equals requested domain
            self.assertEqual(domain_request.creator.status, "restricted")

    def test_user_sets_restricted_status_modal(self):
        """Tests the modal for when a user sets the status to restricted"""
        with less_console_noise():
            # make sure there is no user with this email
            EMAIL = "mayor@igorville.gov"
            User.objects.filter(email=EMAIL).delete()

            # Create a sample domain request
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

            p = "userpass"
            self.client.login(username="staffuser", password=p)
            response = self.client.get(
                "/admin/registrar/domainrequest/{}/change/".format(domain_request.pk),
                follow=True,
            )

            self.assertEqual(response.status_code, 200)
            self.assertContains(response, domain_request.requested_domain.name)

            # Check that the modal has the right content
            # Check for the header
            self.assertContains(response, "Are you sure you want to select ineligible status?")

            # Check for some of its body
            self.assertContains(response, "When a domain request is in ineligible status")

            # Check for some of the button content
            self.assertContains(response, "Yes, select ineligible status")

            # Create a mock request
            request = self.factory.post(
                "/admin/registrar/domainrequest{}/change/".format(domain_request.pk), follow=True
            )
            with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
                # Modify the domain request's property
                domain_request.status = DomainRequest.DomainRequestStatus.INELIGIBLE

                # Use the model admin's save_model method
                self.admin.save_model(request, domain_request, form=None, change=True)

            # Test that approved domain exists and equals requested domain
            self.assertEqual(domain_request.creator.status, "restricted")

            # 'Get' to the domain request again
            response = self.client.get(
                "/admin/registrar/domainrequest/{}/change/".format(domain_request.pk),
                follow=True,
            )

            self.assertEqual(response.status_code, 200)
            self.assertContains(response, domain_request.requested_domain.name)

            # The modal should be unchanged
            self.assertContains(response, "Are you sure you want to select ineligible status?")
            self.assertContains(response, "When a domain request is in ineligible status")
            self.assertContains(response, "Yes, select ineligible status")

    def test_readonly_when_restricted_creator(self):
        with less_console_noise():
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)
            with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
                domain_request.creator.status = User.RESTRICTED
                domain_request.creator.save()

            request = self.factory.get("/")
            request.user = self.superuser

            readonly_fields = self.admin.get_readonly_fields(request, domain_request)

            expected_fields = [
                "other_contacts",
                "current_websites",
                "alternative_domains",
                "is_election_board",
                "federal_agency",
                "id",
                "created_at",
                "updated_at",
                "status",
                "rejection_reason",
                "action_needed_reason",
                "federal_agency",
                "creator",
                "investigator",
                "generic_org_type",
                "is_election_board",
                "organization_type",
                "federally_recognized_tribe",
                "state_recognized_tribe",
                "tribe_name",
                "federal_type",
                "organization_name",
                "address_line1",
                "address_line2",
                "city",
                "state_territory",
                "zipcode",
                "urbanization",
                "about_your_organization",
                "authorizing_official",
                "approved_domain",
                "requested_domain",
                "submitter",
                "purpose",
                "no_other_contacts_rationale",
                "anything_else",
                "has_anything_else_text",
                "cisa_representative_email",
                "cisa_representative_first_name",
                "cisa_representative_last_name",
                "has_cisa_representative",
                "is_policy_acknowledged",
                "submission_date",
                "notes",
                "alternative_domains",
            ]

            self.assertEqual(readonly_fields, expected_fields)

    def test_readonly_fields_for_analyst(self):
        with less_console_noise():
            request = self.factory.get("/")  # Use the correct method and path
            request.user = self.staffuser

            readonly_fields = self.admin.get_readonly_fields(request)

            expected_fields = [
                "other_contacts",
                "current_websites",
                "alternative_domains",
                "is_election_board",
                "federal_agency",
                "creator",
                "about_your_organization",
                "requested_domain",
                "approved_domain",
                "alternative_domains",
                "purpose",
                "submitter",
                "no_other_contacts_rationale",
                "anything_else",
                "is_policy_acknowledged",
                "cisa_representative_first_name",
                "cisa_representative_last_name",
                "cisa_representative_email",
            ]

            self.assertEqual(readonly_fields, expected_fields)

    def test_readonly_fields_for_superuser(self):
        with less_console_noise():
            request = self.factory.get("/")  # Use the correct method and path
            request.user = self.superuser

            readonly_fields = self.admin.get_readonly_fields(request)

            expected_fields = [
                "other_contacts",
                "current_websites",
                "alternative_domains",
                "is_election_board",
                "federal_agency",
            ]

            self.assertEqual(readonly_fields, expected_fields)

    def test_saving_when_restricted_creator(self):
        with less_console_noise():
            # Create an instance of the model
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)
            with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
                domain_request.creator.status = User.RESTRICTED
                domain_request.creator.save()

            # Create a request object with a superuser
            request = self.factory.get("/")
            request.user = self.superuser

            with patch("django.contrib.messages.error") as mock_error:
                # Simulate saving the model
                self.admin.save_model(request, domain_request, None, False)

                # Assert that the error message was called with the correct argument
                mock_error.assert_called_once_with(
                    request,
                    "This action is not permitted for domain requests with a restricted creator.",
                )

            # Assert that the status has not changed
            self.assertEqual(domain_request.status, DomainRequest.DomainRequestStatus.IN_REVIEW)

    def test_change_view_with_restricted_creator(self):
        with less_console_noise():
            # Create an instance of the model
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)
            with boto3_mocking.clients.handler_for("sesv2", self.mock_client):
                domain_request.creator.status = User.RESTRICTED
                domain_request.creator.save()

            with patch("django.contrib.messages.warning") as mock_warning:
                # Create a request object with a superuser
                request = self.factory.get("/admin/your_app/domainrequest/{}/change/".format(domain_request.pk))
                request.user = self.superuser

                self.admin.display_restricted_warning(request, domain_request)

                # Assert that the error message was called with the correct argument
                mock_warning.assert_called_once_with(
                    request,
                    "Cannot edit a domain request with a restricted creator.",
                )

    def trigger_saving_approved_to_another_state(self, domain_is_active, another_state, rejection_reason=None):
        """Helper method that triggers domain request state changes from approved to another state,
        with an associated domain that can be either active (READY) or not.

        Used to test errors when saving a change with an active domain, also used to test side effects
        when saving a change goes through."""

        with less_console_noise():
            # Create an instance of the model
            domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.APPROVED)
            domain = Domain.objects.create(name=domain_request.requested_domain.name)
            domain_information = DomainInformation.objects.create(creator=self.superuser, domain=domain)
            domain_request.approved_domain = domain
            domain_request.save()

            # Create a request object with a superuser
            request = self.factory.post("/admin/registrar/domainrequest/{}/change/".format(domain_request.pk))
            request.user = self.superuser

            # Define a custom implementation for is_active
            def custom_is_active(self):
                return domain_is_active  # Override to return True

            # Use ExitStack to combine patch contexts
            with ExitStack() as stack:
                # Patch Domain.is_active and django.contrib.messages.error simultaneously
                stack.enter_context(patch.object(Domain, "is_active", custom_is_active))
                stack.enter_context(patch.object(messages, "error"))

                domain_request.status = another_state

                if another_state == DomainRequest.DomainRequestStatus.ACTION_NEEDED:
                    domain_request.action_needed_reason = domain_request.ActionNeededReasons.OTHER

                domain_request.rejection_reason = rejection_reason

                self.admin.save_model(request, domain_request, None, True)

                # Assert that the error message was called with the correct argument
                if domain_is_active:
                    messages.error.assert_called_once_with(
                        request,
                        "This action is not permitted. The domain " + "is already active.",
                    )
                else:
                    # Assert that the error message was never called
                    messages.error.assert_not_called()

                    self.assertEqual(domain_request.approved_domain, None)

                    # Assert that Domain got Deleted
                    with self.assertRaises(Domain.DoesNotExist):
                        domain.refresh_from_db()

                    # Assert that DomainInformation got Deleted
                    with self.assertRaises(DomainInformation.DoesNotExist):
                        domain_information.refresh_from_db()

    def test_error_when_saving_approved_to_in_review_and_domain_is_active(self):
        self.trigger_saving_approved_to_another_state(True, DomainRequest.DomainRequestStatus.IN_REVIEW)

    def test_error_when_saving_approved_to_action_needed_and_domain_is_active(self):
        self.trigger_saving_approved_to_another_state(True, DomainRequest.DomainRequestStatus.ACTION_NEEDED)

    def test_error_when_saving_approved_to_rejected_and_domain_is_active(self):
        self.trigger_saving_approved_to_another_state(True, DomainRequest.DomainRequestStatus.REJECTED)

    def test_error_when_saving_approved_to_ineligible_and_domain_is_active(self):
        self.trigger_saving_approved_to_another_state(True, DomainRequest.DomainRequestStatus.INELIGIBLE)

    def test_side_effects_when_saving_approved_to_in_review(self):
        self.trigger_saving_approved_to_another_state(False, DomainRequest.DomainRequestStatus.IN_REVIEW)

    def test_side_effects_when_saving_approved_to_action_needed(self):
        self.trigger_saving_approved_to_another_state(False, DomainRequest.DomainRequestStatus.ACTION_NEEDED)

    def test_side_effects_when_saving_approved_to_rejected(self):
        self.trigger_saving_approved_to_another_state(
            False,
            DomainRequest.DomainRequestStatus.REJECTED,
            DomainRequest.RejectionReasons.CONTACTS_OR_ORGANIZATION_LEGITIMACY,
        )

    def test_side_effects_when_saving_approved_to_ineligible(self):
        self.trigger_saving_approved_to_another_state(False, DomainRequest.DomainRequestStatus.INELIGIBLE)

    def test_has_correct_filters(self):
        """
        This test verifies that DomainRequestAdmin has the correct filters set up.

        It retrieves the current list of filters from DomainRequestAdmin
        and checks that it matches the expected list of filters.
        """
        with less_console_noise():
            request = self.factory.get("/")
            request.user = self.superuser

            # Grab the current list of table filters
            readonly_fields = self.admin.get_list_filter(request)
            expected_fields = (
                DomainRequestAdmin.StatusListFilter,
                "generic_org_type",
                "federal_type",
                DomainRequestAdmin.ElectionOfficeFilter,
                "rejection_reason",
                DomainRequestAdmin.InvestigatorFilter,
            )

            self.assertEqual(readonly_fields, expected_fields)

    def test_table_sorted_alphabetically(self):
        """
        This test verifies that the DomainRequestAdmin table is sorted alphabetically
        by the 'requested_domain__name' field.

        It creates a list of DomainRequest instances in a non-alphabetical order,
        then retrieves the queryset from the DomainRequestAdmin and checks
        that it matches the expected queryset,
        which is sorted alphabetically by the 'requested_domain__name' field.
        """
        with less_console_noise():
            # Creates a list of DomainRequests in scrambled order
            multiple_unalphabetical_domain_objects("domain_request")

            request = self.factory.get("/")
            request.user = self.superuser

            # Get the expected list of alphabetically sorted DomainRequests
            expected_order = DomainRequest.objects.order_by("requested_domain__name")

            # Get the returned queryset
            queryset = self.admin.get_queryset(request)

            # Check the order
            self.assertEqual(
                list(queryset),
                list(expected_order),
            )

    def test_displays_investigator_filter(self):
        """
        This test verifies that the investigator filter in the admin interface for
        the DomainRequest model displays correctly.

        It creates two DomainRequest instances, each with a different investigator.
        It then simulates a staff user logging in and applying the investigator filter
        on the DomainRequest admin page.

        We then test if the page displays the filter we expect, but we do not test
        if we get back the correct response in the table. This is to isolate if
        the filter displays correctly, when the filter isn't filtering correctly.
        """

        with less_console_noise():
            # Create a mock DomainRequest object, with a fake investigator
            domain_request: DomainRequest = generic_domain_object("domain_request", "SomeGuy")
            investigator_user = User.objects.filter(username=domain_request.investigator.username).get()
            investigator_user.is_staff = True
            investigator_user.save()

            p = "userpass"
            self.client.login(username="staffuser", password=p)
            response = self.client.get(
                "/admin/registrar/domainrequest/",
                {
                    "investigator__id__exact": investigator_user.id,
                },
                follow=True,
            )

            # Then, test if the filter actually exists
            self.assertIn("filters", response.context)

            # Assert the content of filters and search_query
            filters = response.context["filters"]

            self.assertEqual(
                filters,
                [
                    {
                        "parameter_name": "investigator",
                        "parameter_value": "SomeGuy first_name:investigator SomeGuy last_name:investigator",
                    },
                ],
            )

    def test_investigator_dropdown_displays_only_staff(self):
        """
        This test verifies that the dropdown for the 'investigator' field in the DomainRequestAdmin
        interface only displays users who are marked as staff.

        It creates two DomainRequest instances, one with an investigator
        who is a staff user and another with an investigator who is not a staff user.

        It then retrieves the queryset for the 'investigator' dropdown from DomainRequestAdmin
        and checks that it matches the expected queryset, which only includes staff users.
        """

        with less_console_noise():
            # Create a mock DomainRequest object, with a fake investigator
            domain_request: DomainRequest = generic_domain_object("domain_request", "SomeGuy")
            investigator_user = User.objects.filter(username=domain_request.investigator.username).get()
            investigator_user.is_staff = True
            investigator_user.save()

            # Create a mock DomainRequest object, with a user that is not staff
            domain_request_2: DomainRequest = generic_domain_object("domain_request", "SomeOtherGuy")
            investigator_user_2 = User.objects.filter(username=domain_request_2.investigator.username).get()
            investigator_user_2.is_staff = False
            investigator_user_2.save()

            p = "userpass"
            self.client.login(username="staffuser", password=p)

            request = self.factory.post("/admin/registrar/domainrequest/{}/change/".format(domain_request.pk))

            # Get the actual field from the model's meta information
            investigator_field = DomainRequest._meta.get_field("investigator")

            # We should only be displaying staff users, in alphabetical order
            sorted_fields = ["first_name", "last_name", "email"]
            expected_dropdown = list(User.objects.filter(is_staff=True).order_by(*sorted_fields))

            # Grab the current dropdown. We do an API call to autocomplete to get this info.
            domain_request_queryset = self.admin.formfield_for_foreignkey(investigator_field, request).queryset
            user_request = self.factory.post(
                "/admin/autocomplete/?app_label=registrar&model_name=domainrequest&field_name=investigator"
            )
            user_admin = MyUserAdmin(User, self.site)
            user_queryset = user_admin.get_search_results(user_request, domain_request_queryset, None)[0]
            current_dropdown = list(user_queryset)

            self.assertEqual(expected_dropdown, current_dropdown)

            # Non staff users should not be in the list
            self.assertNotIn(domain_request_2, current_dropdown)

    def test_investigator_list_is_alphabetically_sorted(self):
        """
        This test verifies that filter list for the 'investigator'
        is displayed alphabetically
        """
        with less_console_noise():
            # Create a mock DomainRequest object, with a fake investigator
            domain_request: DomainRequest = generic_domain_object("domain_request", "SomeGuy")
            investigator_user = User.objects.filter(username=domain_request.investigator.username).get()
            investigator_user.is_staff = True
            investigator_user.save()

            domain_request_2: DomainRequest = generic_domain_object("domain_request", "AGuy")
            investigator_user_2 = User.objects.filter(username=domain_request_2.investigator.username).get()
            investigator_user_2.first_name = "AGuy"
            investigator_user_2.is_staff = True
            investigator_user_2.save()

            domain_request_3: DomainRequest = generic_domain_object("domain_request", "FinalGuy")
            investigator_user_3 = User.objects.filter(username=domain_request_3.investigator.username).get()
            investigator_user_3.first_name = "FinalGuy"
            investigator_user_3.is_staff = True
            investigator_user_3.save()

            p = "userpass"
            self.client.login(username="staffuser", password=p)
            request = RequestFactory().get("/")

            # These names have metadata embedded in them. :investigator implicitly tests if
            # these are actually from the attribute "investigator".
            expected_list = [
                "AGuy AGuy last_name:investigator",
                "FinalGuy FinalGuy last_name:investigator",
                "SomeGuy first_name:investigator SomeGuy last_name:investigator",
            ]

            # Get the actual sorted list of investigators from the lookups method
            actual_list = [item for _, item in self.admin.InvestigatorFilter.lookups(self, request, self.admin)]

            self.assertEqual(expected_list, actual_list)

    @less_console_noise_decorator
    def test_staff_can_see_cisa_region_federal(self):
        """Tests if staff can see CISA Region: N/A"""

        # Create a fake domain request
        _domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)

        p = "userpass"
        self.client.login(username="staffuser", password=p)
        response = self.client.get(
            "/admin/registrar/domainrequest/{}/change/".format(_domain_request.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, _domain_request.requested_domain.name)

        # Test if the page has the right CISA region
        expected_html = '<div class="flex-container margin-top-2"><span>CISA region: N/A</span></div>'
        # Remove whitespace from expected_html
        expected_html = "".join(expected_html.split())

        # Remove whitespace from response content
        response_content = "".join(response.content.decode().split())

        # Check if response contains expected_html
        self.assertIn(expected_html, response_content)

    @less_console_noise_decorator
    def test_staff_can_see_cisa_region_non_federal(self):
        """Tests if staff can see the correct CISA region"""

        # Create a fake domain request. State will be NY (2).
        _domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.IN_REVIEW, generic_org_type="interstate"
        )

        p = "userpass"
        self.client.login(username="staffuser", password=p)
        response = self.client.get(
            "/admin/registrar/domainrequest/{}/change/".format(_domain_request.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, _domain_request.requested_domain.name)

        # Test if the page has the right CISA region
        expected_html = '<div class="flex-container margin-top-2"><span>CISA region: 2</span></div>'
        # Remove whitespace from expected_html
        expected_html = "".join(expected_html.split())

        # Remove whitespace from response content
        response_content = "".join(response.content.decode().split())

        # Check if response contains expected_html
        self.assertIn(expected_html, response_content)

    def tearDown(self):
        super().tearDown()
        Domain.objects.all().delete()
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        User.objects.all().delete()
        Contact.objects.all().delete()
        Website.objects.all().delete()
        self.mock_client.EMAILS_SENT.clear()


class TestDomainInvitationAdmin(TestCase):
    """Tests for the DomainInvitation page"""

    def setUp(self):
        """Create a client object"""
        self.client = Client(HTTP_HOST="localhost:8080")
        self.factory = RequestFactory()
        self.admin = ListHeaderAdmin(model=DomainInvitationAdmin, admin_site=AdminSite())
        self.superuser = create_superuser()

    def tearDown(self):
        """Delete all DomainInvitation objects"""
        DomainInvitation.objects.all().delete()
        User.objects.all().delete()
        Contact.objects.all().delete()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/domaininvitation/",
            follow=True,
        )

        # Make sure that the page is loaded correctly
        self.assertEqual(response.status_code, 200)

        # Test for a description snippet
        self.assertContains(
            response, "Domain invitations contain all individuals who have been invited to manage a .gov domain."
        )
        self.assertContains(response, "Show more")

    def test_get_filters(self):
        """Ensures that our filters are displaying correctly"""
        with less_console_noise():
            # Have to get creative to get past linter
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            response = self.client.get(
                "/admin/registrar/domaininvitation/",
                {},
                follow=True,
            )

            # Assert that the filters are added
            self.assertContains(response, "invited", count=4)
            self.assertContains(response, "Invited", count=2)
            self.assertContains(response, "retrieved", count=2)
            self.assertContains(response, "Retrieved", count=2)

            # Check for the HTML context specificially
            invited_html = '<a href="?status__exact=invited">Invited</a>'
            retrieved_html = '<a href="?status__exact=retrieved">Retrieved</a>'

            self.assertContains(response, invited_html, count=1)
            self.assertContains(response, retrieved_html, count=1)


class TestHostAdmin(TestCase):
    def setUp(self):
        """Setup environment for a mock admin user"""
        super().setUp()
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.admin = MyHostAdmin(model=Host, admin_site=self.site)
        self.client = Client(HTTP_HOST="localhost:8080")
        self.superuser = create_superuser()
        self.test_helper = GenericTestHelper(
            factory=self.factory,
            user=self.superuser,
            admin=self.admin,
            url="/admin/registrar/Host/",
            model=Host,
        )

    def tearDown(self):
        super().tearDown()
        Host.objects.all().delete()
        Domain.objects.all().delete()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/host/",
            follow=True,
        )

        # Make sure that the page is loaded correctly
        self.assertEqual(response.status_code, 200)

        # Test for a description snippet
        self.assertContains(response, "Entries in the Hosts table indicate the relationship between an approved domain")
        self.assertContains(response, "Show more")

    @less_console_noise_decorator
    def test_helper_text(self):
        """
        Tests for the correct helper text on this page
        """
        domain, _ = Domain.objects.get_or_create(name="fake.gov", state=Domain.State.READY)
        # Create a fake host
        host, _ = Host.objects.get_or_create(name="ns1.test.gov", domain=domain)

        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/host/{}/change/".format(host.pk),
            follow=True,
        )

        # Make sure the page loaded
        self.assertEqual(response.status_code, 200)

        # These should exist in the response
        expected_values = [
            ("domain", "Domain associated with this host"),
        ]
        self.test_helper.assert_response_contains_distinct_values(response, expected_values)


class TestDomainInformationAdmin(TestCase):
    def setUp(self):
        """Setup environment for a mock admin user"""
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.admin = DomainInformationAdmin(model=DomainInformation, admin_site=self.site)
        self.client = Client(HTTP_HOST="localhost:8080")
        self.superuser = create_superuser()
        self.staffuser = create_user()
        self.mock_data_generator = AuditedAdminMockData()

        self.test_helper = GenericTestHelper(
            factory=self.factory,
            user=self.superuser,
            admin=self.admin,
            url="/admin/registrar/DomainInformation/",
            model=DomainInformation,
        )

        # Create fake DomainInformation objects
        DomainInformation.objects.create(
            creator=self.mock_data_generator.dummy_user("fake", "creator"),
            domain=self.mock_data_generator.dummy_domain("Apple"),
            submitter=self.mock_data_generator.dummy_contact("Zebra", "submitter"),
        )

        DomainInformation.objects.create(
            creator=self.mock_data_generator.dummy_user("fake", "creator"),
            domain=self.mock_data_generator.dummy_domain("Zebra"),
            submitter=self.mock_data_generator.dummy_contact("Apple", "submitter"),
        )

        DomainInformation.objects.create(
            creator=self.mock_data_generator.dummy_user("fake", "creator"),
            domain=self.mock_data_generator.dummy_domain("Circus"),
            submitter=self.mock_data_generator.dummy_contact("Xylophone", "submitter"),
        )

        DomainInformation.objects.create(
            creator=self.mock_data_generator.dummy_user("fake", "creator"),
            domain=self.mock_data_generator.dummy_domain("Xylophone"),
            submitter=self.mock_data_generator.dummy_contact("Circus", "submitter"),
        )

    def tearDown(self):
        """Delete all Users, Domains, and UserDomainRoles"""
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        Domain.objects.all().delete()
        Contact.objects.all().delete()
        User.objects.all().delete()

    @less_console_noise_decorator
    def test_admin_can_see_cisa_region_federal(self):
        """Tests if admins can see CISA Region: N/A"""

        # Create a fake domain request
        _domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)
        _domain_request.approve()

        domain_information = DomainInformation.objects.filter(domain_request=_domain_request).get()

        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/domaininformation/{}/change/".format(domain_information.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain_information.domain.name)

        # Test if the page has the right CISA region
        expected_html = '<div class="flex-container margin-top-2"><span>CISA region: N/A</span></div>'
        # Remove whitespace from expected_html
        expected_html = "".join(expected_html.split())

        # Remove whitespace from response content
        response_content = "".join(response.content.decode().split())

        # Check if response contains expected_html
        self.assertIn(expected_html, response_content)

    @less_console_noise_decorator
    def test_admin_can_see_cisa_region_non_federal(self):
        """Tests if admins can see the correct CISA region"""

        # Create a fake domain request. State will be NY (2).
        _domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.IN_REVIEW, generic_org_type="interstate"
        )
        _domain_request.approve()

        domain_information = DomainInformation.objects.filter(domain_request=_domain_request).get()
        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/domaininformation/{}/change/".format(domain_information.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain_information.domain.name)

        # Test if the page has the right CISA region
        expected_html = '<div class="flex-container margin-top-2"><span>CISA region: 2</span></div>'
        # Remove whitespace from expected_html
        expected_html = "".join(expected_html.split())

        # Remove whitespace from response content
        response_content = "".join(response.content.decode().split())

        # Check if response contains expected_html
        self.assertIn(expected_html, response_content)

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/domaininformation/",
            follow=True,
        )

        # Make sure that the page is loaded correctly
        self.assertEqual(response.status_code, 200)

        # Test for a description snippet
        self.assertContains(response, "Domain information represents the basic metadata")
        self.assertContains(response, "Show more")

    @less_console_noise_decorator
    def test_helper_text(self):
        """
        Tests for the correct helper text on this page
        """

        # Create a fake domain request and domain
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)
        domain_request.approve()
        domain_info = DomainInformation.objects.filter(domain=domain_request.approved_domain).get()

        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/domaininformation/{}/change/".format(domain_info.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain_info.domain.name)

        # These should exist in the response
        expected_values = [
            ("creator", "Person who submitted the domain request"),
            ("submitter", 'Person listed under "your contact information" in the request form'),
            ("domain_request", "Request associated with this domain"),
            ("no_other_contacts_rationale", "Required if creator does not list other employees"),
            ("urbanization", "Required for Puerto Rico only"),
        ]
        self.test_helper.assert_response_contains_distinct_values(response, expected_values)

    @less_console_noise_decorator
    def test_other_contacts_has_readonly_link(self):
        """Tests if the readonly other_contacts field has links"""

        # Create a fake domain request and domain
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)
        domain_request.approve()
        domain_info = DomainInformation.objects.filter(domain=domain_request.approved_domain).get()

        # Get the other contact
        other_contact = domain_info.other_contacts.all().first()

        p = "adminpass"
        self.client.login(username="superuser", password=p)

        response = self.client.get(
            "/admin/registrar/domaininformation/{}/change/".format(domain_info.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain_info.domain.name)

        # Check that the page contains the url we expect
        expected_href = reverse("admin:registrar_contact_change", args=[other_contact.id])
        self.assertContains(response, expected_href)

        # Check that the page contains the link we expect.
        # Since the url is dynamic (populated by JS), we can test for its existence
        # by checking for the end tag.
        expected_url = "Testy Tester</a>"
        self.assertContains(response, expected_url)

    @less_console_noise_decorator
    def test_analyst_cant_access_domain_information(self):
        """Ensures that analysts can't directly access the DomainInformation page through /admin"""
        # Create fake creator
        _creator = User.objects.create(
            username="MrMeoward",
            first_name="Meoward",
            last_name="Jones",
        )

        # Create a fake domain request
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW, user=_creator)
        domain_request.approve()
        domain_info = DomainInformation.objects.filter(domain=domain_request.approved_domain).get()

        p = "userpass"
        self.client.login(username="staffuser", password=p)
        response = self.client.get(
            "/admin/registrar/domaininformation/{}/change/".format(domain_info.pk),
            follow=True,
        )

        # Make sure that we're denied access
        self.assertEqual(response.status_code, 403)

        # To make sure that its not a fluke, swap to an admin user
        # and try to access the same page. This should succeed.
        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/domaininformation/{}/change/".format(domain_info.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain_info.domain.name)

    @less_console_noise_decorator
    def test_contact_fields_have_detail_table(self):
        """Tests if the contact fields have the detail table which displays title, email, and phone"""

        # Create fake creator
        _creator = User.objects.create(
            username="MrMeoward",
            first_name="Meoward",
            last_name="Jones",
        )

        # Due to the relation between User <==> Contact,
        # the underlying contact has to be modified this way.
        _creator.contact.email = "meoward.jones@igorville.gov"
        _creator.contact.phone = "(555) 123 12345"
        _creator.contact.title = "Treat inspector"
        _creator.contact.save()

        # Create a fake domain request
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW, user=_creator)
        domain_request.approve()
        domain_info = DomainInformation.objects.filter(domain=domain_request.approved_domain).get()

        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/domaininformation/{}/change/".format(domain_info.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain_info.domain.name)

        # Check that the modal has the right content
        # Check for the header

        # == Check for the creator == #

        # Check for the right title, email, and phone number in the response.
        # We only need to check for the end tag
        # (Otherwise this test will fail if we change classes, etc)
        expected_creator_fields = [
            # Field, expected value
            ("title", "Treat inspector"),
            ("email", "meoward.jones@igorville.gov"),
            ("phone", "(555) 123 12345"),
        ]
        self.test_helper.assert_response_contains_distinct_values(response, expected_creator_fields)

        # Check for the field itself
        self.assertContains(response, "Meoward Jones")

        # == Check for the submitter == #
        self.assertContains(response, "mayor@igorville.gov", count=2)
        expected_submitter_fields = [
            # Field, expected value
            ("title", "Admin Tester"),
            ("phone", "(555) 555 5556"),
        ]
        self.test_helper.assert_response_contains_distinct_values(response, expected_submitter_fields)
        self.assertContains(response, "Testy2 Tester2")

        # == Check for the authorizing_official == #
        self.assertContains(response, "testy@town.com", count=2)
        expected_ao_fields = [
            # Field, expected value
            ("title", "Chief Tester"),
            ("phone", "(555) 555 5555"),
        ]
        self.test_helper.assert_response_contains_distinct_values(response, expected_ao_fields)

        self.assertContains(response, "Testy Tester", count=10)

        # == Test the other_employees field == #
        self.assertContains(response, "testy2@town.com", count=2)
        expected_other_employees_fields = [
            # Field, expected value
            ("title", "Another Tester"),
            ("phone", "(555) 555 5557"),
        ]
        self.test_helper.assert_response_contains_distinct_values(response, expected_other_employees_fields)

        # Test for the copy link
        self.assertContains(response, "usa-button__clipboard", count=4)

    def test_readonly_fields_for_analyst(self):
        """Ensures that analysts have their permissions setup correctly"""
        with less_console_noise():
            request = self.factory.get("/")
            request.user = self.staffuser

            readonly_fields = self.admin.get_readonly_fields(request)

            expected_fields = [
                "other_contacts",
                "is_election_board",
                "federal_agency",
                "creator",
                "type_of_work",
                "more_organization_information",
                "domain",
                "domain_request",
                "submitter",
                "no_other_contacts_rationale",
                "anything_else",
                "is_policy_acknowledged",
            ]

            self.assertEqual(readonly_fields, expected_fields)

    def test_domain_sortable(self):
        """Tests if DomainInformation sorts by domain correctly"""
        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            # Assert that our sort works correctly
            self.test_helper.assert_table_sorted("1", ("domain__name",))

            # Assert that sorting in reverse works correctly
            self.test_helper.assert_table_sorted("-1", ("-domain__name",))

    def test_submitter_sortable(self):
        """Tests if DomainInformation sorts by submitter correctly"""
        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            # Assert that our sort works correctly
            self.test_helper.assert_table_sorted(
                "4",
                ("submitter__first_name", "submitter__last_name"),
            )

            # Assert that sorting in reverse works correctly
            self.test_helper.assert_table_sorted("-4", ("-submitter__first_name", "-submitter__last_name"))


class TestUserDomainRoleAdmin(TestCase):
    def setUp(self):
        """Setup environment for a mock admin user"""
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.admin = UserDomainRoleAdmin(model=UserDomainRole, admin_site=self.site)
        self.client = Client(HTTP_HOST="localhost:8080")
        self.superuser = create_superuser()
        self.test_helper = GenericTestHelper(
            factory=self.factory,
            user=self.superuser,
            admin=self.admin,
            url="/admin/registrar/UserDomainRole/",
            model=UserDomainRole,
        )

    def tearDown(self):
        """Delete all Users, Domains, and UserDomainRoles"""
        User.objects.all().delete()
        Domain.objects.all().delete()
        UserDomainRole.objects.all().delete()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/userdomainrole/",
            follow=True,
        )

        # Make sure that the page is loaded correctly
        self.assertEqual(response.status_code, 200)

        # Test for a description snippet
        self.assertContains(
            response, "This table represents the managers who are assigned to each domain in the registrar"
        )
        self.assertContains(response, "Show more")

    def test_domain_sortable(self):
        """Tests if the UserDomainrole sorts by domain correctly"""
        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            fake_user = User.objects.create(
                username="dummyuser", first_name="Stewart", last_name="Jones", email="AntarcticPolarBears@example.com"
            )

            # Create a list of UserDomainRoles that are in random order
            mocks_to_create = ["jkl.gov", "ghi.gov", "abc.gov", "def.gov"]
            for name in mocks_to_create:
                fake_domain = Domain.objects.create(name=name)
                UserDomainRole.objects.create(user=fake_user, domain=fake_domain, role="manager")

            # Assert that our sort works correctly
            self.test_helper.assert_table_sorted("2", ("domain__name",))

            # Assert that sorting in reverse works correctly
            self.test_helper.assert_table_sorted("-2", ("-domain__name",))

    def test_user_sortable(self):
        """Tests if the UserDomainrole sorts by user correctly"""
        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            mock_data_generator = AuditedAdminMockData()

            fake_domain = Domain.objects.create(name="igorville.gov")
            # Create a list of UserDomainRoles that are in random order
            mocks_to_create = ["jkl", "ghi", "abc", "def"]
            for name in mocks_to_create:
                # Creates a fake "User" object
                fake_user = mock_data_generator.dummy_user(name, "user")
                UserDomainRole.objects.create(user=fake_user, domain=fake_domain, role="manager")

            # Assert that our sort works correctly
            self.test_helper.assert_table_sorted("1", ("user__first_name", "user__last_name"))

            # Assert that sorting in reverse works correctly
            self.test_helper.assert_table_sorted("-1", ("-user__first_name", "-user__last_name"))

    def test_email_not_in_search(self):
        """Tests the search bar in Django Admin for UserDomainRoleAdmin.
        Should return no results for an invalid email."""
        with less_console_noise():
            # Have to get creative to get past linter
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            fake_user = User.objects.create(
                username="dummyuser", first_name="Stewart", last_name="Jones", email="AntarcticPolarBears@example.com"
            )
            fake_domain = Domain.objects.create(name="test123")
            UserDomainRole.objects.create(user=fake_user, domain=fake_domain, role="manager")
            # Make the request using the Client class
            # which handles CSRF
            # Follow=True handles the redirect
            response = self.client.get(
                "/admin/registrar/userdomainrole/",
                {
                    "q": "testmail@igorville.com",
                },
                follow=True,
            )

            # Assert that the query is added to the extra_context
            self.assertIn("search_query", response.context)
            # Assert the content of filters and search_query
            search_query = response.context["search_query"]
            self.assertEqual(search_query, "testmail@igorville.com")

            # We only need to check for the end of the HTML string
            self.assertNotContains(response, "Stewart Jones AntarcticPolarBears@example.com</a></th>")

    def test_email_in_search(self):
        """Tests the search bar in Django Admin for UserDomainRoleAdmin.
        Should return results for an valid email."""
        with less_console_noise():
            # Have to get creative to get past linter
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            fake_user = User.objects.create(
                username="dummyuser", first_name="Joe", last_name="Jones", email="AntarcticPolarBears@example.com"
            )
            fake_domain = Domain.objects.create(name="fake")
            UserDomainRole.objects.create(user=fake_user, domain=fake_domain, role="manager")
            # Make the request using the Client class
            # which handles CSRF
            # Follow=True handles the redirect
            response = self.client.get(
                "/admin/registrar/userdomainrole/",
                {
                    "q": "AntarcticPolarBears@example.com",
                },
                follow=True,
            )

            # Assert that the query is added to the extra_context
            self.assertIn("search_query", response.context)

            search_query = response.context["search_query"]
            self.assertEqual(search_query, "AntarcticPolarBears@example.com")

            # We only need to check for the end of the HTML string
            self.assertContains(response, "Joe Jones AntarcticPolarBears@example.com</a></th>", count=1)


class TestListHeaderAdmin(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.admin = ListHeaderAdmin(model=DomainRequest, admin_site=None)
        self.client = Client(HTTP_HOST="localhost:8080")
        self.superuser = create_superuser()

    def test_changelist_view(self):
        with less_console_noise():
            # Have to get creative to get past linter
            p = "adminpass"
            self.client.login(username="superuser", password=p)
            # Mock a user
            user = mock_user()
            # Make the request using the Client class
            # which handles CSRF
            # Follow=True handles the redirect
            response = self.client.get(
                "/admin/registrar/domainrequest/",
                {
                    "status__exact": "started",
                    "investigator__id__exact": user.id,
                    "q": "Hello",
                },
                follow=True,
            )
            # Assert that the filters and search_query are added to the extra_context
            self.assertIn("filters", response.context)
            self.assertIn("search_query", response.context)
            # Assert the content of filters and search_query
            filters = response.context["filters"]
            search_query = response.context["search_query"]
            self.assertEqual(search_query, "Hello")
            self.assertEqual(
                filters,
                [
                    {"parameter_name": "status", "parameter_value": "started"},
                    {
                        "parameter_name": "investigator",
                        "parameter_value": user.first_name + " " + user.last_name,
                    },
                ],
            )

    def test_get_filters(self):
        with less_console_noise():
            # Create a mock request object
            request = self.factory.get("/admin/yourmodel/")
            # Set the GET parameters for testing
            request.GET = {
                "status": "started",
                "investigator": "Jeff Lebowski",
                "q": "search_value",
            }
            # Call the get_filters method
            filters = self.admin.get_filters(request)
            # Assert the filters extracted from the request GET
            self.assertEqual(
                filters,
                [
                    {"parameter_name": "status", "parameter_value": "started"},
                    {"parameter_name": "investigator", "parameter_value": "Jeff Lebowski"},
                ],
            )

    def tearDown(self):
        # delete any domain requests too
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        User.objects.all().delete()


class TestMyUserAdmin(MockDb):
    def setUp(self):
        super().setUp()
        admin_site = AdminSite()
        self.admin = MyUserAdmin(model=get_user_model(), admin_site=admin_site)
        self.client = Client(HTTP_HOST="localhost:8080")
        self.superuser = create_superuser()
        self.staffuser = create_user()
        self.test_helper = GenericTestHelper(admin=self.admin)

    def tearDown(self):
        super().tearDown()
        DomainRequest.objects.all().delete()
        User.objects.all().delete()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/user/",
            follow=True,
        )

        # Make sure that the page is loaded correctly
        self.assertEqual(response.status_code, 200)

        # Test for a description snippet
        self.assertContains(response, "A user is anyone who has access to the registrar.")
        self.assertContains(response, "Show more")

    @less_console_noise_decorator
    def test_helper_text(self):
        """
        Tests for the correct helper text on this page
        """
        user = self.staffuser

        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/user/{}/change/".format(user.pk),
            follow=True,
        )

        # Make sure the page loaded
        self.assertEqual(response.status_code, 200)

        # These should exist in the response
        expected_values = [
            ("password", "Raw passwords are not stored, so they will not display here."),
            ("status", 'Users in "restricted" status cannot make updates in the registrar or start a new request.'),
            ("is_staff", "Designates whether the user can log in to this admin site"),
            ("is_superuser", "For development purposes only; provides superuser access on the database level"),
        ]
        self.test_helper.assert_response_contains_distinct_values(response, expected_values)

    @less_console_noise_decorator
    def test_list_display_without_username(self):
        with less_console_noise():
            request = self.client.request().wsgi_request
            request.user = self.staffuser

            list_display = self.admin.get_list_display(request)
            expected_list_display = [
                "email",
                "first_name",
                "last_name",
                "group",
                "status",
            ]

            self.assertEqual(list_display, expected_list_display)
            self.assertNotIn("username", list_display)

    def test_get_fieldsets_superuser(self):
        with less_console_noise():
            request = self.client.request().wsgi_request
            request.user = self.superuser
            fieldsets = self.admin.get_fieldsets(request)

            expected_fieldsets = super(MyUserAdmin, self.admin).get_fieldsets(request)
            self.assertEqual(fieldsets, expected_fieldsets)

    def test_get_fieldsets_cisa_analyst(self):
        with less_console_noise():
            request = self.client.request().wsgi_request
            request.user = self.staffuser
            fieldsets = self.admin.get_fieldsets(request)
            expected_fieldsets = (
                (
                    None,
                    {
                        "fields": (
                            "status",
                            "verification_type",
                        )
                    },
                ),
                ("Personal Info", {"fields": ("first_name", "middle_name", "last_name", "title", "email", "phone")}),
                ("Permissions", {"fields": ("is_active", "groups")}),
                ("Important dates", {"fields": ("last_login", "date_joined")}),
            )
            self.assertEqual(fieldsets, expected_fieldsets)

    def test_analyst_can_see_related_domains_and_requests_in_user_form(self):
        """Tests if an analyst can see the related domains and domain requests for a user in that user's form"""

        # From MockDb, we have self.meoward_user which we'll use as creator
        # Create fake domain requests
        domain_request_started = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED, user=self.meoward_user, name="started.gov"
        )
        domain_request_submitted = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.SUBMITTED, user=self.meoward_user, name="submitted.gov"
        )
        domain_request_in_review = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.IN_REVIEW, user=self.meoward_user, name="in-review.gov"
        )
        domain_request_withdrawn = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.WITHDRAWN, user=self.meoward_user, name="withdrawn.gov"
        )
        domain_request_approved = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.APPROVED, user=self.meoward_user, name="approved.gov"
        )
        domain_request_rejected = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.REJECTED, user=self.meoward_user, name="rejected.gov"
        )
        domain_request_ineligible = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.INELIGIBLE, user=self.meoward_user, name="ineligible.gov"
        )

        # From MockDb, we have sel.meoward_user who's admin on
        # self.domain_1 - READY
        # self.domain_2 - DNS_NEEDED
        # self.domain_11 - READY
        # self.domain_12 - READY
        # DELETED:
        domain_deleted, _ = Domain.objects.get_or_create(
            name="domain_deleted.gov", state=Domain.State.DELETED, deleted=timezone.make_aware(datetime(2024, 4, 2))
        )
        _, created = UserDomainRole.objects.get_or_create(
            user=self.meoward_user, domain=domain_deleted, role=UserDomainRole.Roles.MANAGER
        )

        p = "userpass"
        self.client.login(username="staffuser", password=p)
        response = self.client.get(
            "/admin/registrar/user/{}/change/".format(self.meoward_user.id),
            follow=True,
        )

        # Make sure the page loaded and contains the expected domain request names and links to the domain requests
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, domain_request_submitted.requested_domain.name)
        expected_href = reverse("admin:registrar_domainrequest_change", args=[domain_request_submitted.pk])
        self.assertContains(response, expected_href)

        self.assertContains(response, domain_request_in_review.requested_domain.name)
        expected_href = reverse("admin:registrar_domainrequest_change", args=[domain_request_in_review.pk])
        self.assertContains(response, expected_href)

        self.assertContains(response, domain_request_approved.requested_domain.name)
        expected_href = reverse("admin:registrar_domainrequest_change", args=[domain_request_approved.pk])
        self.assertContains(response, expected_href)

        self.assertContains(response, domain_request_rejected.requested_domain.name)
        expected_href = reverse("admin:registrar_domainrequest_change", args=[domain_request_rejected.pk])
        self.assertContains(response, expected_href)

        self.assertContains(response, domain_request_ineligible.requested_domain.name)
        expected_href = reverse("admin:registrar_domainrequest_change", args=[domain_request_ineligible.pk])
        self.assertContains(response, expected_href)

        # We filter out those requests
        # STARTED
        self.assertNotContains(response, domain_request_started.requested_domain.name)
        expected_href = reverse("admin:registrar_domainrequest_change", args=[domain_request_started.pk])
        self.assertNotContains(response, expected_href)

        # WITHDRAWN
        self.assertNotContains(response, domain_request_withdrawn.requested_domain.name)
        expected_href = reverse("admin:registrar_domainrequest_change", args=[domain_request_withdrawn.pk])
        self.assertNotContains(response, expected_href)

        # Make sure the page contains the expected domain names and links to the domains
        self.assertContains(response, self.domain_1.name)
        expected_href = reverse("admin:registrar_domain_change", args=[self.domain_1.pk])
        self.assertContains(response, expected_href)

        # We filter out DELETED
        self.assertNotContains(response, domain_deleted.name)
        expected_href = reverse("admin:registrar_domain_change", args=[domain_deleted.pk])
        self.assertNotContains(response, expected_href)


class AuditedAdminTest(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.client = Client(HTTP_HOST="localhost:8080")

    def order_by_desired_field_helper(self, obj_to_sort: AuditedAdmin, request, field_name, *obj_names):
        with less_console_noise():
            formatted_sort_fields = []
            for obj in obj_names:
                formatted_sort_fields.append("{}__{}".format(field_name, obj))

            ordered_list = list(
                obj_to_sort.get_queryset(request).order_by(*formatted_sort_fields).values_list(*formatted_sort_fields)
            )

            return ordered_list

    def test_alphabetically_sorted_domain_request_investigator(self):
        """Tests if the investigator field is alphabetically sorted by mimicking
        the call event flow"""
        # Creates multiple domain requests - review status does not matter
        domain_requests = multiple_unalphabetical_domain_objects("domain_request")

        # Create a mock request
        domain_request_request = self.factory.post(
            "/admin/registrar/domainrequest/{}/change/".format(domain_requests[0].pk)
        )

        # Get the formfield data from the domain request page
        domain_request_admin = AuditedAdmin(DomainRequest, self.site)
        field = DomainRequest.investigator.field
        domain_request_queryset = domain_request_admin.formfield_for_foreignkey(field, domain_request_request).queryset

        request = self.factory.post(
            "/admin/autocomplete/?app_label=registrar&model_name=domainrequest&field_name=investigator"
        )

        sorted_fields = ["first_name", "last_name", "email"]
        desired_sort_order = list(User.objects.filter(is_staff=True).order_by(*sorted_fields))

        # Grab the data returned from get search results
        admin = MyUserAdmin(User, self.site)
        search_queryset = admin.get_search_results(request, domain_request_queryset, None)[0]
        current_sort_order = list(search_queryset)

        self.assertEqual(
            desired_sort_order,
            current_sort_order,
            "Investigator is not ordered alphabetically",
        )

    # This test case should be refactored in general, as it is too overly specific and engineered
    def test_alphabetically_sorted_fk_fields_domain_request(self):
        with less_console_noise():
            tested_fields = [
                DomainRequest.authorizing_official.field,
                DomainRequest.submitter.field,
                # DomainRequest.investigator.field,
                DomainRequest.creator.field,
                DomainRequest.requested_domain.field,
            ]

            # Creates multiple domain requests - review status does not matter
            domain_requests = multiple_unalphabetical_domain_objects("domain_request")

            # Create a mock request
            request = self.factory.post("/admin/registrar/domainrequest/{}/change/".format(domain_requests[0].pk))

            model_admin = AuditedAdmin(DomainRequest, self.site)

            sorted_fields = []
            # Typically we wouldn't want two nested for fields,
            # but both fields are of a fixed length.
            # For test case purposes, this should be performant.
            for field in tested_fields:
                with self.subTest(field=field):
                    isNamefield: bool = field == DomainRequest.requested_domain.field
                    if isNamefield:
                        sorted_fields = ["name"]
                    else:
                        sorted_fields = ["first_name", "last_name"]
                    # We want both of these to be lists, as it is richer test wise.

                    desired_order = self.order_by_desired_field_helper(model_admin, request, field.name, *sorted_fields)
                    current_sort_order = list(model_admin.formfield_for_foreignkey(field, request).queryset)

                    # Conforms to the same object structure as desired_order
                    current_sort_order_coerced_type = []

                    # This is necessary as .queryset and get_queryset
                    # return lists of different types/structures.
                    # We need to parse this data and coerce them into the same type.
                    for contact in current_sort_order:
                        if not isNamefield:
                            first = contact.first_name
                            last = contact.last_name
                        else:
                            first = contact.name
                            last = None

                        name_tuple = self.coerced_fk_field_helper(first, last, field.name, ":")
                        if name_tuple is not None:
                            current_sort_order_coerced_type.append(name_tuple)

                    self.assertEqual(
                        desired_order,
                        current_sort_order_coerced_type,
                        "{} is not ordered alphabetically".format(field.name),
                    )

    def test_alphabetically_sorted_fk_fields_domain_information(self):
        with less_console_noise():
            tested_fields = [
                DomainInformation.authorizing_official.field,
                DomainInformation.submitter.field,
                # DomainInformation.creator.field,
                (DomainInformation.domain.field, ["name"]),
                (DomainInformation.domain_request.field, ["requested_domain__name"]),
            ]
            # Creates multiple domain requests - review status does not matter
            domain_requests = multiple_unalphabetical_domain_objects("information")

            # Create a mock request
            request = self.factory.post("/admin/registrar/domaininformation/{}/change/".format(domain_requests[0].pk))

            model_admin = AuditedAdmin(DomainInformation, self.site)

            sorted_fields = []
            # Typically we wouldn't want two nested for fields,
            # but both fields are of a fixed length.
            # For test case purposes, this should be performant.
            for field in tested_fields:
                isOtherOrderfield: bool = isinstance(field, tuple)
                field_obj = None
                if isOtherOrderfield:
                    sorted_fields = field[1]
                    field_obj = field[0]
                else:
                    sorted_fields = ["first_name", "last_name"]
                    field_obj = field
                # We want both of these to be lists, as it is richer test wise.
                desired_order = self.order_by_desired_field_helper(model_admin, request, field_obj.name, *sorted_fields)
                current_sort_order = list(model_admin.formfield_for_foreignkey(field_obj, request).queryset)

                # Conforms to the same object structure as desired_order
                current_sort_order_coerced_type = []

                # This is necessary as .queryset and get_queryset
                # return lists of different types/structures.
                # We need to parse this data and coerce them into the same type.
                for obj in current_sort_order:
                    last = None
                    if not isOtherOrderfield:
                        first = obj.first_name
                        last = obj.last_name
                    elif field_obj == DomainInformation.domain.field:
                        first = obj.name
                    elif field_obj == DomainInformation.domain_request.field:
                        first = obj.requested_domain.name

                    name_tuple = self.coerced_fk_field_helper(first, last, field_obj.name, ":")
                    if name_tuple is not None:
                        current_sort_order_coerced_type.append(name_tuple)

                self.assertEqual(
                    desired_order,
                    current_sort_order_coerced_type,
                    "{} is not ordered alphabetically".format(field_obj.name),
                )

    def test_alphabetically_sorted_fk_fields_domain_invitation(self):
        with less_console_noise():
            tested_fields = [DomainInvitation.domain.field]

            # Creates multiple domain requests - review status does not matter
            domain_requests = multiple_unalphabetical_domain_objects("invitation")

            # Create a mock request
            request = self.factory.post("/admin/registrar/domaininvitation/{}/change/".format(domain_requests[0].pk))

            model_admin = AuditedAdmin(DomainInvitation, self.site)

            sorted_fields = []
            # Typically we wouldn't want two nested for fields,
            # but both fields are of a fixed length.
            # For test case purposes, this should be performant.
            for field in tested_fields:
                sorted_fields = ["name"]
                # We want both of these to be lists, as it is richer test wise.

                desired_order = self.order_by_desired_field_helper(model_admin, request, field.name, *sorted_fields)
                current_sort_order = list(model_admin.formfield_for_foreignkey(field, request).queryset)

                # Conforms to the same object structure as desired_order
                current_sort_order_coerced_type = []

                # This is necessary as .queryset and get_queryset
                # return lists of different types/structures.
                # We need to parse this data and coerce them into the same type.
                for contact in current_sort_order:
                    first = contact.name
                    last = None

                    name_tuple = self.coerced_fk_field_helper(first, last, field.name, ":")
                    if name_tuple is not None:
                        current_sort_order_coerced_type.append(name_tuple)

                self.assertEqual(
                    desired_order,
                    current_sort_order_coerced_type,
                    "{} is not ordered alphabetically".format(field.name),
                )

    def coerced_fk_field_helper(self, first_name, last_name, field_name, queryset_shorthand):
        """Handles edge cases for test cases"""
        if first_name is None:
            raise ValueError("Invalid value for first_name, must be defined")

        returned_tuple = (first_name, last_name)
        # Handles edge case for names - structured strangely
        if last_name is None:
            return (first_name,)

        if first_name.split(queryset_shorthand)[1] == field_name:
            return returned_tuple
        else:
            return None

    def tearDown(self):
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        DomainInvitation.objects.all().delete()


class DomainSessionVariableTest(TestCase):
    """Test cases for session variables in Django Admin"""

    def setUp(self):
        self.factory = RequestFactory()
        self.admin = DomainAdmin(Domain, None)
        self.client = Client(HTTP_HOST="localhost:8080")

    def test_session_vars_set_correctly(self):
        """Checks if session variables are being set correctly"""

        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            dummy_domain_information = generic_domain_object("information", "session")
            request = self.get_factory_post_edit_domain(dummy_domain_information.domain.pk)
            self.populate_session_values(request, dummy_domain_information.domain)
            self.assertEqual(request.session["analyst_action"], "edit")
            self.assertEqual(
                request.session["analyst_action_location"],
                dummy_domain_information.domain.pk,
            )

    def test_session_vars_set_correctly_hardcoded_domain(self):
        """Checks if session variables are being set correctly"""

        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            dummy_domain_information: Domain = generic_domain_object("information", "session")
            dummy_domain_information.domain.pk = 1

            request = self.get_factory_post_edit_domain(dummy_domain_information.domain.pk)
            self.populate_session_values(request, dummy_domain_information.domain)
            self.assertEqual(request.session["analyst_action"], "edit")
            self.assertEqual(request.session["analyst_action_location"], 1)

    def test_session_variables_reset_correctly(self):
        """Checks if incorrect session variables get overridden"""

        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            dummy_domain_information = generic_domain_object("information", "session")
            request = self.get_factory_post_edit_domain(dummy_domain_information.domain.pk)

            self.populate_session_values(request, dummy_domain_information.domain, preload_bad_data=True)

            self.assertEqual(request.session["analyst_action"], "edit")
            self.assertEqual(
                request.session["analyst_action_location"],
                dummy_domain_information.domain.pk,
            )

    def test_session_variables_retain_information(self):
        """Checks to see if session variables retain old information"""

        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            dummy_domain_information_list = multiple_unalphabetical_domain_objects("information")
            for item in dummy_domain_information_list:
                request = self.get_factory_post_edit_domain(item.domain.pk)
                self.populate_session_values(request, item.domain)

                self.assertEqual(request.session["analyst_action"], "edit")
                self.assertEqual(request.session["analyst_action_location"], item.domain.pk)

    def test_session_variables_concurrent_requests(self):
        """Simulates two requests at once"""

        with less_console_noise():
            p = "adminpass"
            self.client.login(username="superuser", password=p)

            info_first = generic_domain_object("information", "session")
            info_second = generic_domain_object("information", "session2")

            request_first = self.get_factory_post_edit_domain(info_first.domain.pk)
            request_second = self.get_factory_post_edit_domain(info_second.domain.pk)

            self.populate_session_values(request_first, info_first.domain, True)
            self.populate_session_values(request_second, info_second.domain, True)

            # Check if anything got nulled out
            self.assertNotEqual(request_first.session["analyst_action"], None)
            self.assertNotEqual(request_second.session["analyst_action"], None)
            self.assertNotEqual(request_first.session["analyst_action_location"], None)
            self.assertNotEqual(request_second.session["analyst_action_location"], None)

            # Check if they are both the same action 'type'
            self.assertEqual(request_first.session["analyst_action"], "edit")
            self.assertEqual(request_second.session["analyst_action"], "edit")

            # Check their locations, and ensure they aren't the same across both
            self.assertNotEqual(
                request_first.session["analyst_action_location"],
                request_second.session["analyst_action_location"],
            )

    def populate_session_values(self, request, domain_object, preload_bad_data=False):
        """Boilerplate for creating mock sessions"""
        request.user = self.client
        request.session = SessionStore()
        request.session.create()
        if preload_bad_data:
            request.session["analyst_action"] = "invalid"
            request.session["analyst_action_location"] = "bad location"
        self.admin.response_change(request, domain_object)

    def get_factory_post_edit_domain(self, primary_key):
        """Posts to registrar domain change
        with the edit domain button 'clicked',
        then returns the factory object"""
        return self.factory.post(
            reverse("admin:registrar_domain_change", args=(primary_key,)),
            {"_edit_domain": "true"},
            follow=True,
        )


class TestContactAdmin(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.client = Client(HTTP_HOST="localhost:8080")
        self.admin = ContactAdmin(model=get_user_model(), admin_site=None)
        self.superuser = create_superuser()
        self.staffuser = create_user()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/contact/",
            follow=True,
        )

        # Make sure that the page is loaded correctly
        self.assertEqual(response.status_code, 200)

        # Test for a description snippet
        self.assertContains(response, "Contacts include anyone who has access to the registrar (known as “users”)")
        self.assertContains(response, "Show more")

    def test_readonly_when_restricted_staffuser(self):
        with less_console_noise():
            request = self.factory.get("/")
            request.user = self.staffuser

            readonly_fields = self.admin.get_readonly_fields(request)

            expected_fields = [
                "user",
            ]

            self.assertEqual(readonly_fields, expected_fields)

    def test_readonly_when_restricted_superuser(self):
        with less_console_noise():
            request = self.factory.get("/")
            request.user = self.superuser

            readonly_fields = self.admin.get_readonly_fields(request)

            expected_fields = []

            self.assertEqual(readonly_fields, expected_fields)

    def test_change_view_for_joined_contact_five_or_less(self):
        """Create a contact, join it to 4 domain requests. The 5th join will be a user.
        Assert that the warning on the contact form lists 5 joins."""
        with less_console_noise():
            self.client.force_login(self.superuser)

            # Create an instance of the model
            contact, _ = Contact.objects.get_or_create(user=self.staffuser)

            # join it to 4 domain requests. The 5th join will be a user.
            domain_request1 = completed_domain_request(submitter=contact, name="city1.gov")
            domain_request2 = completed_domain_request(submitter=contact, name="city2.gov")
            domain_request3 = completed_domain_request(submitter=contact, name="city3.gov")
            domain_request4 = completed_domain_request(submitter=contact, name="city4.gov")

            with patch("django.contrib.messages.warning") as mock_warning:
                # Use the test client to simulate the request
                response = self.client.get(reverse("admin:registrar_contact_change", args=[contact.pk]))

                # Assert that the error message was called with the correct argument
                # Note: The 5th join will be a user.
                mock_warning.assert_called_once_with(
                    response.wsgi_request,
                    "<ul class='messagelist_content-list--unstyled'>"
                    "<li>Joined to DomainRequest: <a href='/admin/registrar/"
                    f"domainrequest/{domain_request1.pk}/change/'>city1.gov</a></li>"
                    "<li>Joined to DomainRequest: <a href='/admin/registrar/"
                    f"domainrequest/{domain_request2.pk}/change/'>city2.gov</a></li>"
                    "<li>Joined to DomainRequest: <a href='/admin/registrar/"
                    f"domainrequest/{domain_request3.pk}/change/'>city3.gov</a></li>"
                    "<li>Joined to DomainRequest: <a href='/admin/registrar/"
                    f"domainrequest/{domain_request4.pk}/change/'>city4.gov</a></li>"
                    "<li>Joined to User: <a href='/admin/registrar/"
                    f"user/{self.staffuser.pk}/change/'>staff@example.com</a></li>"
                    "</ul>",
                )

    def test_change_view_for_joined_contact_five_or_more(self):
        """Create a contact, join it to 5 domain requests. The 6th join will be a user.
        Assert that the warning on the contact form lists 5 joins and a '1 more' ellispsis."""
        with less_console_noise():
            self.client.force_login(self.superuser)
            # Create an instance of the model
            # join it to 5 domain requests. The 6th join will be a user.
            contact, _ = Contact.objects.get_or_create(user=self.staffuser)
            domain_request1 = completed_domain_request(submitter=contact, name="city1.gov")
            domain_request2 = completed_domain_request(submitter=contact, name="city2.gov")
            domain_request3 = completed_domain_request(submitter=contact, name="city3.gov")
            domain_request4 = completed_domain_request(submitter=contact, name="city4.gov")
            domain_request5 = completed_domain_request(submitter=contact, name="city5.gov")
            with patch("django.contrib.messages.warning") as mock_warning:
                # Use the test client to simulate the request
                response = self.client.get(reverse("admin:registrar_contact_change", args=[contact.pk]))
                logger.debug(mock_warning)
                # Assert that the error message was called with the correct argument
                # Note: The 6th join will be a user.
                mock_warning.assert_called_once_with(
                    response.wsgi_request,
                    "<ul class='messagelist_content-list--unstyled'>"
                    "<li>Joined to DomainRequest: <a href='/admin/registrar/"
                    f"domainrequest/{domain_request1.pk}/change/'>city1.gov</a></li>"
                    "<li>Joined to DomainRequest: <a href='/admin/registrar/"
                    f"domainrequest/{domain_request2.pk}/change/'>city2.gov</a></li>"
                    "<li>Joined to DomainRequest: <a href='/admin/registrar/"
                    f"domainrequest/{domain_request3.pk}/change/'>city3.gov</a></li>"
                    "<li>Joined to DomainRequest: <a href='/admin/registrar/"
                    f"domainrequest/{domain_request4.pk}/change/'>city4.gov</a></li>"
                    "<li>Joined to DomainRequest: <a href='/admin/registrar/"
                    f"domainrequest/{domain_request5.pk}/change/'>city5.gov</a></li>"
                    "</ul>"
                    "<p class='font-sans-3xs'>And 1 more...</p>",
                )

    def tearDown(self):
        DomainRequest.objects.all().delete()
        Contact.objects.all().delete()
        User.objects.all().delete()


class TestVerifiedByStaffAdmin(TestCase):
    def setUp(self):
        super().setUp()
        self.site = AdminSite()
        self.superuser = create_superuser()
        self.admin = VerifiedByStaffAdmin(model=VerifiedByStaff, admin_site=self.site)
        self.factory = RequestFactory()
        self.client = Client(HTTP_HOST="localhost:8080")
        self.test_helper = GenericTestHelper(admin=self.admin)

    def tearDown(self):
        super().tearDown()
        VerifiedByStaff.objects.all().delete()
        User.objects.all().delete()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/verifiedbystaff/",
            follow=True,
        )

        # Make sure that the page is loaded correctly
        self.assertEqual(response.status_code, 200)

        # Test for a description snippet
        self.assertContains(
            response, "This table contains users who have been allowed to bypass " "identity proofing through Login.gov"
        )
        self.assertContains(response, "Show more")

    @less_console_noise_decorator
    def test_helper_text(self):
        """
        Tests for the correct helper text on this page
        """
        vip_instance, _ = VerifiedByStaff.objects.get_or_create(email="test@example.com", notes="Test Notes")

        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/verifiedbystaff/{}/change/".format(vip_instance.pk),
            follow=True,
        )

        # Make sure the page loaded
        self.assertEqual(response.status_code, 200)

        # These should exist in the response
        expected_values = [
            ("requestor", "Person who verified this user"),
        ]
        self.test_helper.assert_response_contains_distinct_values(response, expected_values)

    def test_save_model_sets_user_field(self):
        with less_console_noise():
            self.client.force_login(self.superuser)

            # Create an instance of the admin class
            admin_instance = VerifiedByStaffAdmin(model=VerifiedByStaff, admin_site=None)

            # Create a VerifiedByStaff instance
            vip_instance = VerifiedByStaff(email="test@example.com", notes="Test Notes")

            # Create a request object
            request = self.factory.post("/admin/yourapp/VerifiedByStaff/add/")
            request.user = self.superuser

            # Call the save_model method
            admin_instance.save_model(request, vip_instance, None, None)

            # Check that the user field is set to the request.user
            self.assertEqual(vip_instance.requestor, self.superuser)


class TestWebsiteAdmin(TestCase):
    def setUp(self):
        super().setUp()
        self.site = AdminSite()
        self.superuser = create_superuser()
        self.admin = WebsiteAdmin(model=Website, admin_site=self.site)
        self.factory = RequestFactory()
        self.client = Client(HTTP_HOST="localhost:8080")
        self.test_helper = GenericTestHelper(admin=self.admin)

    def tearDown(self):
        super().tearDown()
        Website.objects.all().delete()
        User.objects.all().delete()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/website/",
            follow=True,
        )

        # Make sure that the page is loaded correctly
        self.assertEqual(response.status_code, 200)

        # Test for a description snippet
        self.assertContains(response, "This table lists all the “current websites” and “alternative domains”")
        self.assertContains(response, "Show more")


class TestDraftDomain(TestCase):
    def setUp(self):
        super().setUp()
        self.site = AdminSite()
        self.superuser = create_superuser()
        self.admin = DraftDomainAdmin(model=DraftDomain, admin_site=self.site)
        self.factory = RequestFactory()
        self.client = Client(HTTP_HOST="localhost:8080")
        self.test_helper = GenericTestHelper(admin=self.admin)

    def tearDown(self):
        super().tearDown()
        DraftDomain.objects.all().delete()
        User.objects.all().delete()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/draftdomain/",
            follow=True,
        )

        # Make sure that the page is loaded correctly
        self.assertEqual(response.status_code, 200)

        # Test for a description snippet
        self.assertContains(
            response, "This table represents all “requested domains” that have been saved within a domain"
        )
        self.assertContains(response, "Show more")


class TestFederalAgency(TestCase):
    def setUp(self):
        super().setUp()
        self.site = AdminSite()
        self.superuser = create_superuser()
        self.admin = FederalAgencyAdmin(model=FederalAgency, admin_site=self.site)
        self.factory = RequestFactory()
        self.client = Client(HTTP_HOST="localhost:8080")
        self.test_helper = GenericTestHelper(admin=self.admin)

    def tearDown(self):
        super().tearDown()
        FederalAgency.objects.all().delete()
        User.objects.all().delete()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/federalagency/",
            follow=True,
        )

        # Make sure that the page is loaded correctly
        self.assertEqual(response.status_code, 200)

        # Test for a description snippet
        self.assertContains(response, "This table does not have a description yet.")
        self.assertContains(response, "Show more")


class TestPublicContact(TestCase):
    def setUp(self):
        super().setUp()
        self.site = AdminSite()
        self.superuser = create_superuser()
        self.admin = PublicContactAdmin(model=PublicContact, admin_site=self.site)
        self.factory = RequestFactory()
        self.client = Client(HTTP_HOST="localhost:8080")
        self.test_helper = GenericTestHelper(admin=self.admin)

    def tearDown(self):
        super().tearDown()
        PublicContact.objects.all().delete()
        User.objects.all().delete()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/publiccontact/",
            follow=True,
        )

        # Make sure that the page is loaded correctly
        self.assertEqual(response.status_code, 200)

        # Test for a description snippet
        self.assertContains(response, "Public contacts represent the three registry contact types")
        self.assertContains(response, "Show more")


class TestTransitionDomain(TestCase):
    def setUp(self):
        super().setUp()
        self.site = AdminSite()
        self.superuser = create_superuser()
        self.admin = TransitionDomainAdmin(model=TransitionDomain, admin_site=self.site)
        self.factory = RequestFactory()
        self.client = Client(HTTP_HOST="localhost:8080")
        self.test_helper = GenericTestHelper(admin=self.admin)

    def tearDown(self):
        super().tearDown()
        PublicContact.objects.all().delete()
        User.objects.all().delete()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/transitiondomain/",
            follow=True,
        )

        # Make sure that the page is loaded correctly
        self.assertEqual(response.status_code, 200)

        # Test for a description snippet
        self.assertContains(response, "This table represents the domains that were transitioned from the old registry")
        self.assertContains(response, "Show more")


class TestUserGroup(TestCase):
    def setUp(self):
        super().setUp()
        self.site = AdminSite()
        self.superuser = create_superuser()
        self.admin = UserGroupAdmin(model=UserGroup, admin_site=self.site)
        self.factory = RequestFactory()
        self.client = Client(HTTP_HOST="localhost:8080")
        self.test_helper = GenericTestHelper(admin=self.admin)

    def tearDown(self):
        super().tearDown()
        User.objects.all().delete()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        p = "adminpass"
        self.client.login(username="superuser", password=p)
        response = self.client.get(
            "/admin/registrar/usergroup/",
            follow=True,
        )

        # Make sure that the page is loaded correctly
        self.assertEqual(response.status_code, 200)

        # Test for a description snippet
        self.assertContains(
            response, "Groups are a way to bundle admin permissions so they can be easily assigned to multiple users."
        )
        self.assertContains(response, "Show more")
