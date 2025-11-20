from datetime import date
from django.test import TestCase, RequestFactory, Client, override_settings
from django.contrib.admin.sites import AdminSite
from api.tests.common import less_console_noise_decorator
from django_webtest import WebTest  # type: ignore
from django.contrib import messages
from django.urls import reverse
from registrar.admin import (
    DomainAdmin,
)
from registrar.models import (
    Domain,
    DomainRequest,
    DomainInformation,
    DomainInvitation,
    User,
    Host,
    Portfolio,
)
from registrar.models.federal_agency import FederalAgency
from registrar.models.public_contact import PublicContact
from registrar.models.user_domain_role import UserDomainRole
from registrar.utility.constants import BranchChoices
from .common import (
    MockSESClient,
    completed_domain_request,
    less_console_noise,
    create_superuser,
    create_user,
    create_omb_analyst_user,
    create_ready_domain,
    MockEppLib,
    GenericTestHelper,
)
from unittest.mock import ANY, call, patch, PropertyMock

import boto3_mocking  # type: ignore
import logging

logger = logging.getLogger(__name__)


class TestDomainAdminAsStaff(MockEppLib):
    """Test DomainAdmin class as staff user.

    Notes:
      all tests share staffuser; do not change staffuser model in tests
      tests have available staffuser, client, and admin
    """

    @classmethod
    def setUpClass(self):
        super().setUpClass()
        self.superuser = create_superuser()
        self.staffuser = create_user()
        self.omb_analyst = create_omb_analyst_user()
        self.site = AdminSite()
        self.admin = DomainAdmin(model=Domain, admin_site=self.site)
        self.factory = RequestFactory()

    def setUp(self):
        self.client = Client(HTTP_HOST="localhost:8080")
        self.client.force_login(self.staffuser)
        self.nonfebdomain = Domain.objects.create(name="nonfebexample.com")
        self.febdomain = Domain.objects.create(name="febexample.com", state=Domain.State.READY)
        self.fed_agency = FederalAgency.objects.create(
            agency="New FedExec Agency", federal_type=BranchChoices.EXECUTIVE
        )
        self.portfolio = Portfolio.objects.create(
            organization_name="new portfolio",
            organization_type=DomainRequest.OrganizationChoices.FEDERAL,
            federal_agency=self.fed_agency,
            requester=self.staffuser,
        )
        self.domain_info = DomainInformation.objects.create(
            domain=self.febdomain, portfolio=self.portfolio, requester=self.staffuser
        )
        self.nonfebportfolio = Portfolio.objects.create(
            organization_name="non feb portfolio",
            requester=self.staffuser,
        )
        super().setUp()

    def tearDown(self):
        super().tearDown()
        Host.objects.all().delete()
        PublicContact.objects.all().delete()
        Domain.objects.all().delete()
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        Portfolio.objects.all().delete()
        self.fed_agency.delete()

    @classmethod
    def tearDownClass(self):
        User.objects.all().delete()
        super().tearDownClass()

    @less_console_noise_decorator
    def test_omb_analyst_view(self):
        """Ensure OMB analysts can view domain list."""
        self.client.force_login(self.omb_analyst)
        response = self.client.get(reverse("admin:registrar_domain_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.febdomain.name)
        self.assertNotContains(response, self.nonfebdomain.name)
        self.assertNotContains(response, ">Import<")
        self.assertNotContains(response, ">Export<")

    @less_console_noise_decorator
    def test_omb_analyst_change(self):
        """Ensure OMB analysts can view/edit federal executive branch domains."""
        self.client.force_login(self.omb_analyst)
        response = self.client.get(reverse("admin:registrar_domain_change", args=[self.nonfebdomain.id]))
        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse("admin:registrar_domain_change", args=[self.febdomain.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.febdomain.name)
        # test portfolio dropdown
        self.assertContains(response, self.portfolio.organization_name)
        self.assertNotContains(response, self.nonfebportfolio.organization_name)
        # test buttons
        self.assertNotContains(response, "Manage domain")
        self.assertNotContains(response, "Get registry status")
        self.assertNotContains(response, "Extend expiration date")
        self.assertNotContains(response, "Remove from registry")
        self.assertNotContains(response, "Place hold")
        self.assertContains(response, "Save")
        self.assertNotContains(response, ">Delete<")
        # test whether fields are readonly or editable
        self.assertNotContains(response, "id_domain_info-0-portfolio")
        self.assertNotContains(response, "id_domain_info-0-sub_organization")
        self.assertNotContains(response, "id_domain_info-0-requester")
        self.assertNotContains(response, "id_domain_info-0-federal_agency")
        self.assertNotContains(response, "id_domain_info-0-about_your_organization")
        self.assertNotContains(response, "id_domain_info-0-anything_else")
        self.assertNotContains(response, "id_domain_info-0-cisa_representative_first_name")
        self.assertNotContains(response, "id_domain_info-0-cisa_representative_last_name")
        self.assertNotContains(response, "id_domain_info-0-cisa_representative_email")
        self.assertNotContains(response, "id_domain_info-0-domain_request")
        self.assertNotContains(response, "id_domain_info-0-notes")
        self.assertNotContains(response, "id_domain_info-0-senior_official")
        self.assertNotContains(response, "id_domain_info-0-organization_type")
        self.assertNotContains(response, "id_domain_info-0-state_territory")
        self.assertNotContains(response, "id_domain_info-0-address_line1")
        self.assertNotContains(response, "id_domain_info-0-address_line2")
        self.assertNotContains(response, "id_domain_info-0-city")
        self.assertNotContains(response, "id_domain_info-0-zipcode")
        self.assertNotContains(response, "id_domain_info-0-urbanization")
        self.assertNotContains(response, "id_domain_info-0-portfolio_organization_type")
        self.assertNotContains(response, "id_domain_info-0-portfolio_federal_type")
        self.assertNotContains(response, "id_domain_info-0-portfolio_organization_name")
        self.assertNotContains(response, "id_domain_info-0-portfolio_federal_agency")
        self.assertNotContains(response, "id_domain_info-0-portfolio_state_territory")
        self.assertNotContains(response, "id_domain_info-0-portfolio_address_line1")
        self.assertNotContains(response, "id_domain_info-0-portfolio_address_line2")
        self.assertNotContains(response, "id_domain_info-0-portfolio_city")
        self.assertNotContains(response, "id_domain_info-0-portfolio_zipcode")
        self.assertNotContains(response, "id_domain_info-0-portfolio_urbanization")
        self.assertNotContains(response, "id_domain_info-0-organization_type")
        self.assertNotContains(response, "id_domain_info-0-federal_type")
        self.assertNotContains(response, "id_domain_info-0-federal_agency")
        self.assertNotContains(response, "id_domain_info-0-tribe_name")
        self.assertNotContains(response, "id_domain_info-0-federally_recognized_tribe")
        self.assertNotContains(response, "id_domain_info-0-state_recognized_tribe")
        self.assertNotContains(response, "id_domain_info-0-about_your_organization")
        self.assertNotContains(response, "id_domain_info-0-portfolio")
        self.assertNotContains(response, "id_domain_info-0-sub_organization")

    @less_console_noise_decorator
    def test_superuser_change(self):
        """Ensure super user can view/edit all domains."""
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:registrar_domain_change", args=[self.nonfebdomain.id]))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse("admin:registrar_domain_change", args=[self.febdomain.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.febdomain.name)
        # test portfolio dropdown
        self.assertContains(response, self.portfolio.organization_name)
        # test buttons
        self.assertContains(response, "Manage domain")
        self.assertContains(response, "Get registry status")
        self.assertContains(response, "Extend expiration date")
        self.assertContains(response, "Remove from registry")
        self.assertContains(response, "Place hold")
        self.assertContains(response, "Save")
        self.assertContains(response, ">Delete<")
        # test whether fields are readonly or editable
        self.assertContains(response, "id_domain_info-0-portfolio")
        self.assertContains(response, "id_domain_info-0-sub_organization")
        self.assertContains(response, "id_domain_info-0-requester")
        self.assertContains(response, "id_domain_info-0-federal_agency")
        self.assertContains(response, "id_domain_info-0-about_your_organization")
        self.assertContains(response, "id_domain_info-0-anything_else")
        self.assertContains(response, "id_domain_info-0-cisa_representative_first_name")
        self.assertContains(response, "id_domain_info-0-cisa_representative_last_name")
        self.assertContains(response, "id_domain_info-0-cisa_representative_email")
        self.assertContains(response, "id_domain_info-0-domain_request")
        self.assertContains(response, "id_domain_info-0-notes")
        self.assertContains(response, "id_domain_info-0-senior_official")
        self.assertContains(response, "id_domain_info-0-organization_type")
        self.assertContains(response, "id_domain_info-0-state_territory")
        self.assertContains(response, "id_domain_info-0-address_line1")
        self.assertContains(response, "id_domain_info-0-address_line2")
        self.assertContains(response, "id_domain_info-0-city")
        self.assertContains(response, "id_domain_info-0-zipcode")
        self.assertContains(response, "id_domain_info-0-urbanization")
        self.assertContains(response, "id_domain_info-0-organization_type")
        self.assertContains(response, "id_domain_info-0-federal_type")
        self.assertContains(response, "id_domain_info-0-federal_agency")
        self.assertContains(response, "id_domain_info-0-tribe_name")
        self.assertContains(response, "id_domain_info-0-federally_recognized_tribe")
        self.assertContains(response, "id_domain_info-0-state_recognized_tribe")
        self.assertContains(response, "id_domain_info-0-about_your_organization")
        self.assertContains(response, "id_domain_info-0-portfolio")
        self.assertContains(response, "id_domain_info-0-sub_organization")

    @less_console_noise_decorator
    def test_staff_can_see_cisa_region_federal(self):
        """Tests if staff can see CISA Region: N/A"""

        # Create a fake domain request
        _domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)
        _domain_request.approve()

        domain = _domain_request.approved_domain
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
    def test_analyst_can_see_inline_domain_information_in_domain_change_form(self):
        """Tests if an analyst can still see the inline domain information form"""

        # Create fake requester
        _requester = User.objects.create(
            username="MrMeoward",
            first_name="Meoward",
            last_name="Jones",
        )

        # Create a fake domain request
        _domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW, user=_requester)

        # Creates a Domain and DomainInformation object
        _domain_request.approve()

        domain_information = DomainInformation.objects.filter(domain_request=_domain_request).get()
        domain_information.organization_name = "MonkeySeeMonkeyDo"
        domain_information.save()

        # We use filter here rather than just domain_information.domain just to get the latest data.
        domain = Domain.objects.filter(domain_info=domain_information).get()

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
    def test_deletion_is_successful(self):
        """
        Scenario: Domain deletion is successful
            When the domain is deleted
            Then a user-friendly success message is returned for displaying on the web
            And `state` is set to `DELETED`
        """
        domain, _ = Domain.objects.get_or_create(name="my-nameserver.gov", state=Domain.State.READY)
        # Put in client hold
        domain.place_client_hold()
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
                "Domain my-nameserver.gov has been deleted. Thanks!",
                extra_tags="",
                fail_silently=False,
            )

        # The modal should still exist
        self.assertContains(response, "Are you sure you want to remove this domain from the registry?")
        self.assertContains(response, "When a domain is removed from the registry:")
        self.assertContains(response, "Yes, remove from registry")

        self.assertEqual(domain.state, Domain.State.DELETED)

    @less_console_noise_decorator
    def test_deletion_is_unsuccessful(self):
        """
        Scenario: Domain deletion is unsuccessful
            When the domain is deleted and has shared subdomains
            Then a user-friendly success message is returned for displaying on the web
            And `state` is not set to `DELETED`
        """
        domain, _ = Domain.objects.get_or_create(name="sharingiscaring.gov", state=Domain.State.ON_HOLD)
        # Put in client hold
        domain.place_client_hold()
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
                messages.ERROR,
                "Error deleting this Domain: Command failed with note: Domain has associated objects that prevent deletion.",  # noqa
                extra_tags="",
                fail_silently=False,
            )

        self.assertEqual(domain.state, Domain.State.ON_HOLD)

    @less_console_noise_decorator
    def test_deletion_ready_fsm_failure(self):
        """
        Scenario: Domain deletion is unsuccessful
            When an error is returned from epplibwrapper
            Then a user-friendly error message is returned for displaying on the web
            And `state` is not set to `DELETED`
        """

        domain = create_ready_domain()
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

    @less_console_noise_decorator
    def test_analyst_deletes_domain_idempotent(self):
        """
        Scenario: Analyst tries to delete an already deleted domain
            Given `state` is already `DELETED`
            When `domain.deleteInEpp()` is called
            Then `commands.DeleteDomain` is sent to the registry
            And Domain returns normally without an error dialog
        """
        domain, _ = Domain.objects.get_or_create(name="my-nameserver.gov", state=Domain.State.READY)
        # Put in client hold
        domain.place_client_hold()
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
                "Domain my-nameserver.gov has been deleted. Thanks!",
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

    def test_has_correct_filters_staff_view(self):
        """Ensure DomainAdmin has the correct filters configured."""
        with less_console_noise():
            request = self.factory.get("/")
            request.user = self.superuser

            filters = self.admin.get_list_filter(request)

            expected_filters = [
                DomainAdmin.GenericOrgFilter,
                DomainAdmin.FederalTypeFilter,
                DomainAdmin.ElectionOfficeFilter,
                "state",
            ]

            self.assertEqual(filters, expected_filters)

    def test_on_hold_columns_display(self):
        """Test that 'on hold date' and 'days on hold' columns display correctly in Domain in /admin
        when a domain is put on hold, and when the hold is removed.
        We are using PropertyMock as on_hold_date and days_on_hold are both properties"""
        fixed_on_hold_day = date(2025, 5, 29)

        with patch.object(Domain, "on_hold_date", new_callable=PropertyMock) as mock_on_hold_date, patch.object(
            Domain, "days_on_hold", new_callable=PropertyMock
        ) as mock_days_on_hold:

            mock_on_hold_date.return_value = fixed_on_hold_day
            mock_days_on_hold.return_value = 0

            # 1. Create domain in READY state
            domain = Domain.objects.create(
                name="put-on-hold-then-remove-hold.gov",
                state=Domain.State.READY,
            )

            # 2. Transition domain to ON_HOLD
            domain.place_client_hold(ignoreEPP=True)
            domain.save()

            # 3. Grab the admin display values for on hold date + days on hold
            on_hold_date_display = self.admin.on_hold_date_display(domain)
            days_on_hold_display = self.admin.days_on_hold_display(domain)

            # 4. Check for correct date, count, and type
            self.assertEqual(on_hold_date_display, fixed_on_hold_day)
            self.assertEqual(days_on_hold_display, 0)
            self.assertIsInstance(on_hold_date_display, date)
            self.assertIsInstance(days_on_hold_display, int)

            # 5. Confirm headers are correct
            self.assertEqual(self.admin.on_hold_date_display.short_description, "On hold date")
            self.assertEqual(self.admin.days_on_hold_display.short_description, "Days on hold")

        # 6. Remove hold, domain transitions back to READY
        domain.revert_client_hold(ignoreEPP=True)
        domain.save()

        # 7. Grab the admin display values for on hold date + days on hold
        on_hold_date_display = self.admin.on_hold_date_display(domain)
        days_on_hold_display = self.admin.days_on_hold_display(domain)

        # 8. Since hold is removed, both should return None
        self.assertIsNone(on_hold_date_display)
        self.assertIsNone(days_on_hold_display)


class TestDomainInformationInline(MockEppLib):
    """Test DomainAdmin class, specifically the DomainInformationInline class, as staff user.

    Notes:
      all tests share staffuser; do not change staffuser model in tests
      tests have available staffuser, client, and admin
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.staffuser = create_user()
        cls.site = AdminSite()
        cls.admin = DomainAdmin(model=Domain, admin_site=cls.site)
        cls.factory = RequestFactory()

    def setUp(self):
        self.client = Client(HTTP_HOST="localhost:8080")
        self.client.force_login(self.staffuser)
        super().setUp()

    def tearDown(self):
        super().tearDown()
        Host.objects.all().delete()
        UserDomainRole.objects.all().delete()
        Domain.objects.all().delete()
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        User.objects.all().delete()
        super().tearDownClass()

    @less_console_noise_decorator
    def test_domain_managers_display(self):
        """Tests the custom domain managers field"""
        admin_user_1 = User.objects.create(
            username="testuser1",
            first_name="Gerald",
            last_name="Meoward",
            email="meoward@gov.gov",
        )

        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.IN_REVIEW, user=self.staffuser, name="fake.gov"
        )
        domain_request.approve()
        _domain_info = DomainInformation.objects.filter(domain=domain_request.approved_domain).get()
        domain = Domain.objects.filter(domain_info=_domain_info).get()

        UserDomainRole.objects.get_or_create(user=admin_user_1, domain=domain, role=UserDomainRole.Roles.MANAGER)

        admin_user_2 = User.objects.create(
            username="testuser2",
            first_name="Arnold",
            last_name="Poopy",
            email="poopy@gov.gov",
        )

        UserDomainRole.objects.get_or_create(user=admin_user_2, domain=domain, role=UserDomainRole.Roles.MANAGER)

        # Get the first inline (DomainInformationInline)
        inline_instance = self.admin.inlines[0](self.admin.model, self.admin.admin_site)

        # Call the domain_managers method
        domain_managers = inline_instance.domain_managers(domain.domain_info)

        self.assertIn(
            f'<a href="/admin/registrar/user/{admin_user_1.pk}/change/">testuser1</a>',
            domain_managers,
        )
        self.assertIn("Gerald Meoward", domain_managers)
        self.assertIn("meoward@gov.gov", domain_managers)
        self.assertIn(f'<a href="/admin/registrar/user/{admin_user_2.pk}/change/">testuser2</a>', domain_managers)
        self.assertIn("Arnold Poopy", domain_managers)
        self.assertIn("poopy@gov.gov", domain_managers)

    @less_console_noise_decorator
    def test_invited_domain_managers_display(self):
        """Tests the custom invited domain managers field"""
        admin_user_1 = User.objects.create(
            username="testuser1",
            first_name="Gerald",
            last_name="Meoward",
            email="meoward@gov.gov",
        )

        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.IN_REVIEW, user=self.staffuser, name="fake.gov"
        )
        domain_request.approve()
        _domain_info = DomainInformation.objects.filter(domain=domain_request.approved_domain).get()
        domain = Domain.objects.filter(domain_info=_domain_info).get()

        # domain, _ = Domain.objects.get_or_create(name="fake.gov", state=Domain.State.READY)
        UserDomainRole.objects.get_or_create(user=admin_user_1, domain=domain, role=UserDomainRole.Roles.MANAGER)

        admin_user_2 = User.objects.create(
            username="testuser2",
            first_name="Arnold",
            last_name="Poopy",
            email="poopy@gov.gov",
        )

        UserDomainRole.objects.get_or_create(user=admin_user_2, domain=domain, role=UserDomainRole.Roles.MANAGER)

        # Get the first inline (DomainInformationInline)
        inline_instance = self.admin.inlines[0](self.admin.model, self.admin.admin_site)

        # Call the domain_managers method
        domain_managers = inline_instance.domain_managers(domain.domain_info)
        # domain_managers = self.admin.get_inlinesdomain_managers(self.domain)

        self.assertIn(
            f'<a href="/admin/registrar/user/{admin_user_1.pk}/change/">testuser1</a>',
            domain_managers,
        )
        self.assertIn("Gerald Meoward", domain_managers)
        self.assertIn("meoward@gov.gov", domain_managers)
        self.assertIn(f'<a href="/admin/registrar/user/{admin_user_2.pk}/change/">testuser2</a>', domain_managers)
        self.assertIn("Arnold Poopy", domain_managers)
        self.assertIn("poopy@gov.gov", domain_managers)


class TestDomainInvitationAdmin(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.staffuser = create_user(email="staffdomainmanager@meoward.com", is_staff=True)
        cls.site = AdminSite()
        cls.admin = DomainAdmin(model=Domain, admin_site=cls.site)
        cls.factory = RequestFactory()

    def setUp(self):
        self.client = Client(HTTP_HOST="localhost:8080")
        self.client.force_login(self.staffuser)
        super().setUp()

    def test_successful_cancel_invitation_flow_in_admin(self):
        """Testing canceling a domain invitation in Django Admin."""

        # 1. Create a domain and assign staff user role + domain manager
        domain = Domain.objects.create(name="cancelinvitationflowviaadmin.gov")
        UserDomainRole.objects.create(user=self.staffuser, domain=domain, role="manager")

        # 2. Invite a domain manager to the above domain
        invitation = DomainInvitation.objects.create(
            email="inviteddomainmanager@meoward.com",
            domain=domain,
            status=DomainInvitation.DomainInvitationStatus.INVITED,
        )

        # 3. Go to the Domain Invitations list in /admin
        domain_invitation_list_url = reverse("admin:registrar_domaininvitation_changelist")
        response = self.client.get(domain_invitation_list_url)
        self.assertEqual(response.status_code, 200)

        # 4. Go to the change view of that invitation and make sure you can see the button
        domain_invitation_change_url = reverse("admin:registrar_domaininvitation_change", args=[invitation.id])
        response = self.client.get(domain_invitation_change_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cancel invitation")

        # 5. Click the cancel invitation button
        response = self.client.post(domain_invitation_change_url, {"cancel_invitation": "true"}, follow=True)

        # 6. Make sure we're redirect back to the change view page in /admin
        self.assertRedirects(response, domain_invitation_change_url)

        # 7. Confirm cancellation confirmation message appears
        expected_message = f"Invitation for {invitation.email} on {domain.name} is canceled"
        self.assertContains(response, expected_message)

    def test_no_cancel_invitation_button_in_retrieved_state(self):
        """Shouldn't be able to see the "Cancel invitation" button if invitation is RETRIEVED state"""

        # 1. Create a domain and assign staff user role + domain manager
        domain = Domain.objects.create(name="retrieved.gov")
        UserDomainRole.objects.create(user=self.staffuser, domain=domain, role="manager")

        # 2. Invite a domain manager to the above domain and NOT in invited state
        invitation = DomainInvitation.objects.create(
            email="retrievedinvitation@meoward.com",
            domain=domain,
            status=DomainInvitation.DomainInvitationStatus.RETRIEVED,
        )

        # 3. Go to the Domain Invitations list in /admin
        domain_invitation_list_url = reverse("admin:registrar_domaininvitation_changelist")
        response = self.client.get(domain_invitation_list_url)
        self.assertEqual(response.status_code, 200)

        # 4. Go to the change view of that invitation and make sure you CANNOT see the button
        domain_invitation_change_url = reverse("admin:registrar_domaininvitation_change", args=[invitation.id])
        response = self.client.get(domain_invitation_change_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Cancel invitation")

    def test_no_cancel_invitation_button_in_canceled_state(self):
        """Shouldn't be able to see the "Cancel invitation" button if invitation is CANCELED state"""

        # 1. Create a domain and assign staff user role + domain manager
        domain = Domain.objects.create(name="canceled.gov")
        UserDomainRole.objects.create(user=self.staffuser, domain=domain, role="manager")

        # 2. Invite a domain manager to the above domain and NOT in invited state
        invitation = DomainInvitation.objects.create(
            email="canceledinvitation@meoward.com",
            domain=domain,
            status=DomainInvitation.DomainInvitationStatus.CANCELED,
        )

        # 3. Go to the Domain Invitations list in /admin
        domain_invitation_list_url = reverse("admin:registrar_domaininvitation_changelist")
        response = self.client.get(domain_invitation_list_url)
        self.assertEqual(response.status_code, 200)

        # 4. Go to the change view of that invitation and make sure you CANNOT see the button
        domain_invitation_change_url = reverse("admin:registrar_domaininvitation_change", args=[invitation.id])
        response = self.client.get(domain_invitation_change_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Cancel invitation")


class TestDomainAdminWithClient(TestCase):
    """Test DomainAdmin class as super user.

    Notes:
      all tests share superuser; tests must not update superuser
      tests have available superuser, client, and admin
    """

    @classmethod
    def setUpClass(self):
        super().setUpClass()
        self.site = AdminSite()
        self.admin = DomainAdmin(model=Domain, admin_site=self.site)
        self.factory = RequestFactory()
        self.superuser = create_superuser()

    def setUp(self):
        self.client = Client(HTTP_HOST="localhost:8080")
        self.client.force_login(self.superuser)
        super().setUp()

    def tearDown(self):
        super().tearDown()
        Host.objects.all().delete()
        UserDomainRole.objects.all().delete()
        Domain.objects.all().delete()
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        Portfolio.objects.all().delete()

    @classmethod
    def tearDownClass(self):
        User.objects.all().delete()
        super().tearDownClass()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
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

        # Create fake requester
        _requester = User.objects.create(
            username="MrMeoward",
            first_name="Meoward",
            last_name="Jones",
            email="meoward.jones@igorville.gov",
            phone="(555) 123 12345",
            title="Treat inspector",
        )

        # Create a fake domain request
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW, user=_requester)
        domain_request.approve()
        _domain_info = DomainInformation.objects.filter(domain=domain_request.approved_domain).get()
        domain = Domain.objects.filter(domain_info=_domain_info).get()

        response = self.client.get(
            "/admin/registrar/domain/{}/change/".format(domain.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)

        # Check that the fields have the right values.

        # == Check for the senior_official == #
        self.assertContains(response, "testy@town.com")
        self.assertContains(response, "Chief Tester")
        self.assertContains(response, "(555) 555 5555")

        # Includes things like readonly fields
        self.assertContains(response, "Testy Tester")

        # Test for the copy link
        self.assertContains(response, "copy-to-clipboard")

        # cleanup from this test
        domain.delete()
        _domain_info.delete()
        domain_request.delete()
        _requester.delete()

    @less_console_noise_decorator
    def test_domains_by_portfolio(self):
        """
        Tests that domains display for a portfolio.  And that domains outside the portfolio do not display.
        """

        portfolio, _ = Portfolio.objects.get_or_create(organization_name="Test Portfolio", requester=self.superuser)
        # Create a fake domain request and domain
        _domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.IN_REVIEW, portfolio=portfolio
        )
        _domain_request.approve()

        domain = _domain_request.approved_domain
        domain2, _ = Domain.objects.get_or_create(name="fake.gov", state=Domain.State.READY)
        UserDomainRole.objects.get_or_create()
        UserDomainRole.objects.get_or_create(user=self.superuser, domain=domain2, role=UserDomainRole.Roles.MANAGER)

        self.client.force_login(self.superuser)
        response = self.client.get(
            "/admin/registrar/domain/?portfolio={}".format(portfolio.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)
        self.assertNotContains(response, domain2.name)
        self.assertContains(response, portfolio.organization_name)

    @less_console_noise_decorator
    def test_helper_text(self):
        """
        Tests for the correct helper text on this page
        """

        # Create a ready domain with a preset expiration date
        domain, _ = Domain.objects.get_or_create(name="fake.gov", state=Domain.State.READY)

        response = self.client.get(
            "/admin/registrar/domain/{}/change/".format(domain.pk),
            follow=True,
        )

        # Make sure the page loaded, and that we're on the right page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)

        # Contains some test tools
        test_helper = GenericTestHelper(
            factory=self.factory,
            user=self.superuser,
            admin=self.admin,
            url=reverse("admin:registrar_domain_changelist"),
            model=Domain,
            client=self.client,
        )
        # These should exist in the response
        expected_values = [
            ("expiration_date", "Date the domain expires in the registry"),
            ("first_ready_at", 'Date when this domain first moved into "ready" state; date will never change'),
            ("deleted_at", 'Will appear blank unless the domain is in "deleted" state'),
        ]
        test_helper.assert_response_contains_distinct_values(response, expected_values)

    @less_console_noise_decorator
    def test_helper_text_state(self):
        """
        Tests for the correct state helper text on this page
        """

        # Add domain data
        ready_domain, _ = Domain.objects.get_or_create(name="fakeready.gov", state=Domain.State.READY)
        unknown_domain, _ = Domain.objects.get_or_create(name="fakeunknown.gov", state=Domain.State.UNKNOWN)
        dns_domain, _ = Domain.objects.get_or_create(name="fakedns.gov", state=Domain.State.DNS_NEEDED)
        hold_domain, _ = Domain.objects.get_or_create(name="fakehold.gov", state=Domain.State.ON_HOLD)
        deleted_domain, _ = Domain.objects.get_or_create(name="fakedeleted.gov", state=Domain.State.DELETED)

        # We don't need to check for all text content, just a portion of it
        expected_unknown_domain_message = "The requester of the associated domain request has not logged in to"
        expected_dns_message = "Before this domain can be used, name server addresses need"
        expected_hold_message = "While on hold, this domain"
        expected_deleted_message = "This domain was permanently removed from the registry."
        expected_messages = [
            (ready_domain, "This domain has name servers and is ready for use."),
            (unknown_domain, expected_unknown_domain_message),
            (dns_domain, expected_dns_message),
            (hold_domain, expected_hold_message),
            (deleted_domain, expected_deleted_message),
        ]

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

    @less_console_noise_decorator
    def test_admin_can_see_inline_domain_information_in_domain_change_form(self):
        """Tests if an admin can still see the inline domain information form"""
        # Create fake requester
        _requester = User.objects.create(
            username="MrMeoward",
            first_name="Meoward",
            last_name="Jones",
        )

        # Create a fake domain request
        _domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW, user=_requester)

        # Creates a Domain and DomainInformation object
        _domain_request.approve()

        domain_information = DomainInformation.objects.filter(domain_request=_domain_request).get()
        domain_information.organization_name = "MonkeySeeMonkeyDo"
        domain_information.save()

        # We use filter here rather than just domain_information.domain just to get the latest data.
        domain = Domain.objects.filter(domain_info=domain_information).get()

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

        # cleanup from this test
        domain.delete()
        domain_information.delete()
        _domain_request.delete()
        _requester.delete()

    @less_console_noise_decorator
    def test_custom_delete_confirmation_page_table(self):
        """Tests if we override the delete confirmation page for custom content on the table"""
        # Create a ready domain
        domain, _ = Domain.objects.get_or_create(name="fake.gov", state=Domain.State.READY)

        # Get the index. The post expects the index to be encoded as a string
        index = f"{domain.id}"

        # Contains some test tools
        test_helper = GenericTestHelper(
            factory=self.factory,
            user=self.superuser,
            admin=self.admin,
            url=reverse("admin:registrar_domain_changelist"),
            model=Domain,
            client=self.client,
        )

        # Simulate selecting a single record, then clicking "Delete selected domains"
        response = test_helper.get_table_delete_confirmation_page("0", index)

        # Check that our content exists
        content_slice = "When a domain is deleted:"
        self.assertContains(response, content_slice)

    @less_console_noise_decorator
    def test_short_org_name_in_domains_list(self):
        """
        Make sure the short name is displaying in admin on the list page
        """
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)
        mock_client = MockSESClient()
        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            domain_request.approve()

        response = self.client.get("/admin/registrar/domain/")
        # There are 4 template references to Federal (4) plus four references in the table
        # for our actual domain_request
        self.assertContains(response, "Federal", count=7)
        # This may be a bit more robust
        self.assertContains(response, '<td class="field-converted_generic_org_type">Federal</td>', count=1)
        # Now let's make sure the long description does not exist
        self.assertNotContains(response, "Federal: an agency of the U.S. government")

    @override_settings(IS_PRODUCTION=True)
    @less_console_noise_decorator
    def test_prod_only_shows_export(self):
        """Test that production environment only displays export"""
        response = self.client.get("/admin/registrar/domain/")
        self.assertContains(response, ">Export<")
        self.assertNotContains(response, ">Import<")

    def test_has_correct_filters_client_view(self):
        """Ensure DomainAdmin has the correct filters configured"""
        with less_console_noise():
            request = self.factory.get("/")
            request.user = self.superuser

            filters = self.admin.get_list_filter(request)

            expected_filters = [
                DomainAdmin.GenericOrgFilter,
                DomainAdmin.FederalTypeFilter,
                DomainAdmin.ElectionOfficeFilter,
                "state",
            ]

            self.assertEqual(filters, expected_filters)


class TestDomainAdminWebTest(MockEppLib, WebTest):
    """Test DomainAdmin class as super user, using WebTest.
    WebTest allows for easier handling of forms and html responses.

    Notes:
      all tests share superuser; tests must not update superuser
      tests have available superuser, app, and admin
    """

    # csrf checks do not work with WebTest.
    # We disable them here. TODO for another ticket.
    csrf_checks = False

    @classmethod
    def setUpClass(self):
        super().setUpClass()
        self.site = AdminSite()
        self.admin = DomainAdmin(model=Domain, admin_site=self.site)
        self.superuser = create_superuser()
        self.factory = RequestFactory()

    def setUp(self):
        super().setUp()
        self.app.set_user(self.superuser.username)

    def tearDown(self):
        super().tearDown()
        Host.objects.all().delete()
        Domain.objects.all().delete()
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()

    @classmethod
    def tearDownClass(self):
        User.objects.all().delete()
        super().tearDownClass()

    @less_console_noise_decorator
    @patch("registrar.admin.DomainAdmin._get_current_date", return_value=date(2024, 1, 1))
    def test_extend_expiration_date_button(self, mock_date_today):
        """
        Tests if extend_expiration_date modal gives an accurate date
        """

        # Create a ready domain with a preset expiration date
        domain, _ = Domain.objects.get_or_create(name="fake.gov", state=Domain.State.READY)
        response = self.app.get(reverse("admin:registrar_domain_change", args=[domain.pk]))
        # load expiration date into cache and registrar with below command
        domain.registry_expiration_date
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

        # Assert that it is calling the function with the default extension length.
        # We only need to test the value that EPP sends, as we can assume the other
        # test cases cover the "renew" function.
        renew_mock.assert_has_calls([call()], any_order=False)

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

    @less_console_noise_decorator
    def test_custom_delete_confirmation_page(self):
        """Tests if we override the delete confirmation page for custom content"""
        # Create a ready domain with a preset expiration date
        domain, _ = Domain.objects.get_or_create(name="fake.gov", state=Domain.State.READY)

        domain_change_page = self.app.get(reverse("admin:registrar_domain_change", args=[domain.pk]))

        self.assertContains(domain_change_page, "fake.gov")
        # click the "Delete" link
        confirmation_page = domain_change_page.click("Delete", index=0)

        content_slice = "When a domain is deleted:"
        self.assertContains(confirmation_page, content_slice)

    @less_console_noise_decorator
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
