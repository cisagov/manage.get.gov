from datetime import datetime
from django.utils import timezone
from django.test import TestCase, RequestFactory, Client
from django.contrib.admin.sites import AdminSite
from api.tests.common import less_console_noise_decorator
from django.urls import reverse
from registrar.admin import (
    DomainAdmin,
    DomainInvitationAdmin,
    ListHeaderAdmin,
    MyUserAdmin,
    AuditedAdmin,
    ContactAdmin,
    DomainInformationAdmin,
    MyHostAdmin,
    PortfolioInvitationAdmin,
    UserDomainRoleAdmin,
    VerifiedByStaffAdmin,
    FsmModelResource,
    WebsiteAdmin,
    DraftDomainAdmin,
    FederalAgencyAdmin,
    PublicContactAdmin,
    TransitionDomainAdmin,
    UserGroupAdmin,
    PortfolioAdmin,
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
    Portfolio,
    Suborganization,
)
from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.senior_official import SeniorOfficial
from registrar.models.user_domain_role import UserDomainRole
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices
from registrar.models.verified_by_staff import VerifiedByStaff
from .common import (
    MockDbForSharedTests,
    AuditedAdminMockData,
    completed_domain_request,
    generic_domain_object,
    less_console_noise,
    mock_user,
    create_superuser,
    create_user,
    multiple_unalphabetical_domain_objects,
    GenericTestHelper,
)
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.auth import get_user_model
from unittest.mock import patch, Mock

import logging

logger = logging.getLogger(__name__)


class TestFsmModelResource(TestCase):
    def setUp(self):
        self.resource = FsmModelResource()

    @less_console_noise_decorator
    def test_init_instance(self):
        """Test initializing an instance of a class with a FSM field"""

        # Mock a row with FSMField data
        row_data = {"state": "ready"}

        self.resource._meta.model = Domain

        instance = self.resource.init_instance(row=row_data)

        # Assert that the instance is initialized correctly
        self.assertIsInstance(instance, Domain)
        self.assertEqual(instance.state, "ready")

    @less_console_noise_decorator
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


class TestDomainInvitationAdmin(TestCase):
    """Tests for the DomainInvitationAdmin class as super user

    Notes:
      all tests share superuser; do not change this model in tests
      tests have available superuser, client, and admin
    """

    @classmethod
    def setUpClass(cls):
        cls.factory = RequestFactory()
        cls.admin = ListHeaderAdmin(model=DomainInvitationAdmin, admin_site=AdminSite())
        cls.superuser = create_superuser()

    def setUp(self):
        """Create a client object"""
        self.client = Client(HTTP_HOST="localhost:8080")

    def tearDown(self):
        """Delete all DomainInvitation objects"""
        DomainInvitation.objects.all().delete()
        Contact.objects.all().delete()

    @classmethod
    def tearDownClass(self):
        User.objects.all().delete()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        self.client.force_login(self.superuser)
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
            self.client.force_login(self.superuser)

            response = self.client.get(
                "/admin/registrar/domaininvitation/",
                {},
                follow=True,
            )

            # Assert that the filters are added
            self.assertContains(response, "invited", count=5)
            self.assertContains(response, "Invited", count=2)
            self.assertContains(response, "retrieved", count=2)
            self.assertContains(response, "Retrieved", count=2)

            # Check for the HTML context specificially
            invited_html = '<a href="?status__exact=invited">Invited</a>'
            retrieved_html = '<a href="?status__exact=retrieved">Retrieved</a>'

            self.assertContains(response, invited_html, count=1)
            self.assertContains(response, retrieved_html, count=1)


class TestPortfolioInvitationAdmin(TestCase):
    """Tests for the PortfolioInvitationAdmin class as super user

    Notes:
      all tests share superuser; do not change this model in tests
      tests have available superuser, client, and admin
    """

    @classmethod
    def setUpClass(cls):
        cls.factory = RequestFactory()
        cls.admin = ListHeaderAdmin(model=PortfolioInvitationAdmin, admin_site=AdminSite())
        cls.superuser = create_superuser()

    def setUp(self):
        """Create a client object"""
        self.client = Client(HTTP_HOST="localhost:8080")

    def tearDown(self):
        """Delete all DomainInvitation objects"""
        PortfolioInvitation.objects.all().delete()
        Contact.objects.all().delete()

    @classmethod
    def tearDownClass(self):
        User.objects.all().delete()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        self.client.force_login(self.superuser)
        response = self.client.get(
            "/admin/registrar/portfolioinvitation/",
            follow=True,
        )

        # Make sure that the page is loaded correctly
        self.assertEqual(response.status_code, 200)

        # Test for a description snippet
        self.assertContains(
            response,
            "Portfolio invitations contain all individuals who have been invited to become members of an organization.",
        )
        self.assertContains(response, "Show more")

    def test_get_filters(self):
        """Ensures that our filters are displaying correctly"""
        with less_console_noise():
            self.client.force_login(self.superuser)

            response = self.client.get(
                "/admin/registrar/portfolioinvitation/",
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
    """Tests for the HostAdmin class as super user

    Notes:
      all tests share superuser; do not change this model in tests
      tests have available superuser, client, and admin
    """

    @classmethod
    def setUpClass(cls):
        cls.site = AdminSite()
        cls.factory = RequestFactory()
        cls.admin = MyHostAdmin(model=Host, admin_site=cls.site)
        cls.superuser = create_superuser()

    def setUp(self):
        """Setup environment for a mock admin user"""
        super().setUp()
        self.client = Client(HTTP_HOST="localhost:8080")

    def tearDown(self):
        super().tearDown()
        Host.objects.all().delete()
        Domain.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        User.objects.all().delete()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        self.client.force_login(self.superuser)
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

        self.client.force_login(self.superuser)
        response = self.client.get(
            "/admin/registrar/host/{}/change/".format(host.pk),
            follow=True,
        )

        # Make sure the page loaded
        self.assertEqual(response.status_code, 200)

        self.test_helper = GenericTestHelper(
            factory=self.factory,
            user=self.superuser,
            admin=self.admin,
            url="/admin/registrar/Host/",
            model=Host,
        )
        # These should exist in the response
        expected_values = [
            ("domain", "Domain associated with this host"),
        ]
        self.test_helper.assert_response_contains_distinct_values(response, expected_values)


class TestDomainInformationAdmin(TestCase):
    """Tests for the DomainInformationAdmin class as super or staff user

    Notes:
      all tests share superuser/staffuser; do not change these models in tests
      tests have available staffuser, superuser, client, test_helper and admin
    """

    @classmethod
    def setUpClass(cls):
        """Setup environment for a mock admin user"""
        cls.site = AdminSite()
        cls.factory = RequestFactory()
        cls.admin = DomainInformationAdmin(model=DomainInformation, admin_site=cls.site)
        cls.superuser = create_superuser()
        cls.staffuser = create_user()
        cls.mock_data_generator = AuditedAdminMockData()
        cls.test_helper = GenericTestHelper(
            factory=cls.factory,
            user=cls.superuser,
            admin=cls.admin,
            url="/admin/registrar/DomainInformation/",
            model=DomainInformation,
        )

    def setUp(self):
        self.client = Client(HTTP_HOST="localhost:8080")

    def tearDown(self):
        """Delete all Users, Domains, and UserDomainRoles"""
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        Domain.objects.all().delete()
        Contact.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        User.objects.all().delete()
        SeniorOfficial.objects.all().delete()

    @less_console_noise_decorator
    def test_domain_information_senior_official_is_alphabetically_sorted(self):
        """Tests if the senior offical dropdown is alphanetically sorted in the django admin display"""

        SeniorOfficial.objects.get_or_create(first_name="mary", last_name="joe", title="some other guy")
        SeniorOfficial.objects.get_or_create(first_name="alex", last_name="smoe", title="some guy")
        SeniorOfficial.objects.get_or_create(first_name="Zoup", last_name="Soup", title="title")

        contact, _ = Contact.objects.get_or_create(first_name="Henry", last_name="McFakerson")
        domain_request = completed_domain_request(
            submitter=contact, name="city1244.gov", status=DomainRequest.DomainRequestStatus.IN_REVIEW
        )
        domain_request.approve()

        domain_info = DomainInformation.objects.get(domain_request=domain_request)
        request = self.factory.post("/admin/registrar/domaininformation/{}/change/".format(domain_info.pk))
        model_admin = AuditedAdmin(DomainInformation, self.site)

        # Get the queryset that would be returned for the list
        senior_offical_queryset = model_admin.formfield_for_foreignkey(
            DomainInformation.senior_official.field, request
        ).queryset

        # Make the list we're comparing on a bit prettier display-wise. Optional step.
        current_sort_order = []
        for official in senior_offical_queryset:
            current_sort_order.append(f"{official.first_name} {official.last_name}")

        expected_sort_order = ["alex smoe", "mary joe", "Zoup Soup"]

        self.assertEqual(current_sort_order, expected_sort_order)

    @less_console_noise_decorator
    def test_admin_can_see_cisa_region_federal(self):
        """Tests if admins can see CISA Region: N/A"""

        # Create a fake domain request
        _domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW)
        _domain_request.approve()

        domain_information = DomainInformation.objects.filter(domain_request=_domain_request).get()

        self.client.force_login(self.superuser)
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
        self.client.force_login(self.superuser)
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
        self.client.force_login(self.superuser)
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

        self.client.force_login(self.superuser)
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

        self.client.force_login(self.superuser)

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

        self.client.force_login(self.staffuser)
        response = self.client.get(
            "/admin/registrar/domaininformation/{}/change/".format(domain_info.pk),
            follow=True,
        )

        # Make sure that we're denied access
        self.assertEqual(response.status_code, 403)

        # To make sure that its not a fluke, swap to an admin user
        # and try to access the same page. This should succeed.
        self.client.force_login(self.superuser)
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
            email="meoward.jones@igorville.gov",
            phone="(555) 123 12345",
            title="Treat inspector",
        )

        # Create a fake domain request
        domain_request = completed_domain_request(status=DomainRequest.DomainRequestStatus.IN_REVIEW, user=_creator)
        domain_request.approve()
        domain_info = DomainInformation.objects.filter(domain=domain_request.approved_domain).get()

        self.client.force_login(self.superuser)
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

        # Check for the right title and phone number in the response.
        # We only need to check for the end tag
        # (Otherwise this test will fail if we change classes, etc)
        expected_creator_fields = [
            # Field, expected value
            ("title", "Treat inspector"),
            ("phone", "(555) 123 12345"),
        ]
        self.test_helper.assert_response_contains_distinct_values(response, expected_creator_fields)
        self.assertContains(response, "meoward.jones@igorville.gov")

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

        # == Check for the senior_official == #
        self.assertContains(response, "testy@town.com", count=2)
        expected_so_fields = [
            # Field, expected value
            ("title", "Chief Tester"),
            ("phone", "(555) 555 5555"),
        ]
        self.test_helper.assert_response_contains_distinct_values(response, expected_so_fields)

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
        self.assertContains(response, "button--clipboard", count=4)

        # cleanup this test
        domain_info.delete()
        domain_request.delete()
        _creator.delete()

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
            self.client.force_login(self.superuser)

            # Assert that our sort works correctly
            self.test_helper.assert_table_sorted("1", ("domain__name",))

            # Assert that sorting in reverse works correctly
            self.test_helper.assert_table_sorted("-1", ("-domain__name",))

    def test_submitter_sortable(self):
        """Tests if DomainInformation sorts by submitter correctly"""
        with less_console_noise():
            self.client.force_login(self.superuser)

            # Assert that our sort works correctly
            self.test_helper.assert_table_sorted(
                "4",
                ("submitter__first_name", "submitter__last_name"),
            )

            # Assert that sorting in reverse works correctly
            self.test_helper.assert_table_sorted("-4", ("-submitter__first_name", "-submitter__last_name"))


class TestUserDomainRoleAdmin(TestCase):
    """Tests for the UserDomainRoleAdmin class as super user

    Notes:
      all tests share superuser; do not change this model in tests
      tests have available superuser, client, test_helper and admin
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.site = AdminSite()
        cls.factory = RequestFactory()
        cls.admin = UserDomainRoleAdmin(model=UserDomainRole, admin_site=cls.site)
        cls.superuser = create_superuser()
        cls.test_helper = GenericTestHelper(
            factory=cls.factory,
            user=cls.superuser,
            admin=cls.admin,
            url="/admin/registrar/UserDomainRole/",
            model=UserDomainRole,
        )

    def setUp(self):
        """Setup environment for a mock admin user"""
        super().setUp()
        self.client = Client(HTTP_HOST="localhost:8080")

    def tearDown(self):
        """Delete all Users, Domains, and UserDomainRoles"""
        super().tearDown()
        UserDomainRole.objects.all().delete()
        Domain.objects.all().delete()
        User.objects.exclude(username="superuser").delete()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        User.objects.all().delete()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        self.client.force_login(self.superuser)
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
            self.client.force_login(self.superuser)

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
            self.client.force_login(self.superuser)

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
            self.client.force_login(self.superuser)

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
            self.client.force_login(self.superuser)

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
    """Tests for the ListHeaderAdmin class as super user

    Notes:
      all tests share superuser; do not change this model in tests
      tests have available superuser, client and admin
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.site = AdminSite()
        cls.factory = RequestFactory()
        cls.admin = ListHeaderAdmin(model=DomainRequest, admin_site=None)
        cls.superuser = create_superuser()

    def setUp(self):
        super().setUp()
        self.client = Client(HTTP_HOST="localhost:8080")

    def tearDown(self):
        # delete any domain requests too
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        User.objects.all().delete()

    def test_changelist_view(self):
        with less_console_noise():
            self.client.force_login(self.superuser)
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


class TestMyUserAdmin(MockDbForSharedTests):
    """Tests for the MyUserAdmin class as super or staff user

    Notes:
      all tests share superuser/staffuser; do not change these models in tests
      all tests share MockDb; do not change models defined therein in tests
      tests have available staffuser, superuser, client, test_helper and admin
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        admin_site = AdminSite()
        cls.admin = MyUserAdmin(model=get_user_model(), admin_site=admin_site)
        cls.superuser = create_superuser()
        cls.staffuser = create_user()
        cls.test_helper = GenericTestHelper(admin=cls.admin)

    def setUp(self):
        super().setUp()
        self.client = Client(HTTP_HOST="localhost:8080")

    def tearDown(self):
        super().tearDown()
        DomainRequest.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        User.objects.all().delete()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        self.client.force_login(self.superuser)
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

        self.client.force_login(self.superuser)
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
                ("User profile", {"fields": ("first_name", "middle_name", "last_name", "title", "email", "phone")}),
                (
                    "Permissions",
                    {
                        "fields": (
                            "is_active",
                            "groups",
                        )
                    },
                ),
                ("Important dates", {"fields": ("last_login", "date_joined")}),
            )
            self.assertEqual(fieldsets, expected_fieldsets)

    @less_console_noise_decorator
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
        role, _ = UserDomainRole.objects.get_or_create(
            user=self.meoward_user, domain=domain_deleted, role=UserDomainRole.Roles.MANAGER
        )

        self.client.force_login(self.staffuser)
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

        # Must clean up within test since MockDB is shared across tests for performance reasons
        domain_request_started_id = domain_request_started.id
        domain_request_submitted_id = domain_request_submitted.id
        domain_request_in_review_id = domain_request_in_review.id
        domain_request_withdrawn_id = domain_request_withdrawn.id
        domain_request_approved_id = domain_request_approved.id
        domain_request_rejected_id = domain_request_rejected.id
        domain_request_ineligible_id = domain_request_ineligible.id
        domain_request_ids = [
            domain_request_started_id,
            domain_request_submitted_id,
            domain_request_in_review_id,
            domain_request_withdrawn_id,
            domain_request_approved_id,
            domain_request_rejected_id,
            domain_request_ineligible_id,
        ]
        DomainRequest.objects.filter(id__in=domain_request_ids).delete()
        domain_deleted.delete()
        role.delete()

    def test_analyst_cannot_see_selects_for_portfolio_role_and_permissions_in_user_form(self):
        """Can only test for the presence of a base element. The multiselects and the h2->h3 conversion are all
        dynamically generated."""

        self.client.force_login(self.staffuser)
        response = self.client.get(
            "/admin/registrar/user/{}/change/".format(self.meoward_user.id),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)

        self.assertNotContains(response, "Portfolio roles:")
        self.assertNotContains(response, "Portfolio additional permissions:")


class AuditedAdminTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.site = AdminSite()
        cls.factory = RequestFactory()

    def setUp(self):
        super().setUp()
        self.client = Client(HTTP_HOST="localhost:8080")
        self.staffuser = create_user()

    def tearDown(self):
        super().tearDown()
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        DomainInvitation.objects.all().delete()

    def order_by_desired_field_helper(self, obj_to_sort: AuditedAdmin, request, field_name, *obj_names):
        with less_console_noise():
            formatted_sort_fields = []
            for obj in obj_names:
                formatted_sort_fields.append("{}__{}".format(field_name, obj))

            ordered_list = list(
                obj_to_sort.get_queryset(request).order_by(*formatted_sort_fields).values_list(*formatted_sort_fields)
            )

            return ordered_list

    @less_console_noise_decorator
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
                # Senior offical is commented out for now - this is alphabetized
                # and this test does not accurately reflect that.
                # DomainRequest.senior_official.field,
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
                # Senior offical is commented out for now - this is alphabetized
                # and this test does not accurately reflect that.
                # DomainInformation.senior_official.field,
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

        split_name = first_name.split(queryset_shorthand)
        if len(split_name) == 2 and split_name[1] == field_name:
            return returned_tuple
        else:
            return None


class DomainSessionVariableTest(TestCase):
    """Test cases for session variables in Django Admin"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.admin = DomainAdmin(Domain, None)
        cls.superuser = create_superuser()

    def setUp(self):
        super().setUp()
        self.client = Client(HTTP_HOST="localhost:8080")

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        User.objects.all().delete()

    def test_session_vars_set_correctly(self):
        """Checks if session variables are being set correctly"""

        with less_console_noise():
            self.client.force_login(self.superuser)

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
            self.client.force_login(self.superuser)

            dummy_domain_information: Domain = generic_domain_object("information", "session")
            dummy_domain_information.domain.pk = 1

            request = self.get_factory_post_edit_domain(dummy_domain_information.domain.pk)
            self.populate_session_values(request, dummy_domain_information.domain)
            self.assertEqual(request.session["analyst_action"], "edit")
            self.assertEqual(request.session["analyst_action_location"], 1)

    def test_session_variables_reset_correctly(self):
        """Checks if incorrect session variables get overridden"""

        with less_console_noise():
            self.client.force_login(self.superuser)

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
            self.client.force_login(self.superuser)

            dummy_domain_information_list = multiple_unalphabetical_domain_objects("information")
            for item in dummy_domain_information_list:
                request = self.get_factory_post_edit_domain(item.domain.pk)
                self.populate_session_values(request, item.domain)

                self.assertEqual(request.session["analyst_action"], "edit")
                self.assertEqual(request.session["analyst_action_location"], item.domain.pk)

    def test_session_variables_concurrent_requests(self):
        """Simulates two requests at once"""

        with less_console_noise():
            self.client.force_login(self.superuser)

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

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.site = AdminSite()
        cls.factory = RequestFactory()
        cls.admin = ContactAdmin(model=Contact, admin_site=None)
        cls.superuser = create_superuser()
        cls.staffuser = create_user()

    def setUp(self):
        super().setUp()
        self.client = Client(HTTP_HOST="localhost:8080")

    def tearDown(self):
        super().tearDown()
        DomainRequest.objects.all().delete()
        Contact.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        User.objects.all().delete()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        self.client.force_login(self.superuser)
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

            expected_fields = ["email"]

            self.assertEqual(readonly_fields, expected_fields)

    def test_readonly_when_restricted_superuser(self):
        with less_console_noise():
            request = self.factory.get("/")
            request.user = self.superuser

            readonly_fields = self.admin.get_readonly_fields(request)

            expected_fields = []

            self.assertEqual(readonly_fields, expected_fields)

    def test_change_view_for_joined_contact_five_or_less(self):
        """Create a contact, join it to 4 domain requests.
        Assert that the warning on the contact form lists 4 joins."""
        with less_console_noise():
            self.client.force_login(self.superuser)

            # Create an instance of the model
            contact, _ = Contact.objects.get_or_create(
                first_name="Henry",
                last_name="McFakerson",
            )

            # join it to 4 domain requests.
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
                    "</ul>",
                )

            # cleanup this test
            DomainRequest.objects.all().delete()
            contact.delete()

    def test_change_view_for_joined_contact_five_or_more(self):
        """Create a contact, join it to 6 domain requests.
        Assert that the warning on the contact form lists 5 joins and a '1 more' ellispsis."""
        with less_console_noise():
            self.client.force_login(self.superuser)
            # Create an instance of the model
            # join it to 6 domain requests.
            contact, _ = Contact.objects.get_or_create(
                first_name="Henry",
                last_name="McFakerson",
            )
            domain_request1 = completed_domain_request(submitter=contact, name="city1.gov")
            domain_request2 = completed_domain_request(submitter=contact, name="city2.gov")
            domain_request3 = completed_domain_request(submitter=contact, name="city3.gov")
            domain_request4 = completed_domain_request(submitter=contact, name="city4.gov")
            domain_request5 = completed_domain_request(submitter=contact, name="city5.gov")
            completed_domain_request(submitter=contact, name="city6.gov")
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
            # cleanup this test
            DomainRequest.objects.all().delete()
            contact.delete()


class TestVerifiedByStaffAdmin(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.site = AdminSite()
        cls.superuser = create_superuser()
        cls.admin = VerifiedByStaffAdmin(model=VerifiedByStaff, admin_site=cls.site)
        cls.factory = RequestFactory()
        cls.test_helper = GenericTestHelper(admin=cls.admin)

    def setUp(self):
        super().setUp()
        self.client = Client(HTTP_HOST="localhost:8080")

    def tearDown(self):
        super().tearDown()
        VerifiedByStaff.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        User.objects.all().delete()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        self.client.force_login(self.superuser)
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

        self.client.force_login(self.superuser)
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
        self.client.force_login(self.superuser)
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

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.site = AdminSite()
        cls.superuser = create_superuser()
        cls.admin = DraftDomainAdmin(model=DraftDomain, admin_site=cls.site)
        cls.factory = RequestFactory()
        cls.test_helper = GenericTestHelper(admin=cls.admin)

    def setUp(self):
        super().setUp()
        self.client = Client(HTTP_HOST="localhost:8080")

    def tearDown(self):
        super().tearDown()
        DraftDomain.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        User.objects.all().delete()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        self.client.force_login(self.superuser)
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

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.site = AdminSite()
        cls.superuser = create_superuser()
        cls.admin = FederalAgencyAdmin(model=FederalAgency, admin_site=cls.site)
        cls.factory = RequestFactory()
        cls.test_helper = GenericTestHelper(admin=cls.admin)

    def setUp(self):
        self.client = Client(HTTP_HOST="localhost:8080")

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        User.objects.all().delete()

    @less_console_noise_decorator
    def test_has_model_description(self):
        """Tests if this model has a model description on the table view"""
        self.client.force_login(self.superuser)
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
        self.client.force_login(self.superuser)
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
        self.client.force_login(self.superuser)
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


class TestPortfolioAdmin(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.site = AdminSite()
        cls.superuser = create_superuser()
        cls.admin = PortfolioAdmin(model=Portfolio, admin_site=cls.site)
        cls.factory = RequestFactory()

    def setUp(self):
        self.client = Client(HTTP_HOST="localhost:8080")
        self.portfolio = Portfolio.objects.create(organization_name="Test Portfolio", creator=self.superuser)

    def tearDown(self):
        Suborganization.objects.all().delete()
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        Domain.objects.all().delete()
        Portfolio.objects.all().delete()
        User.objects.all().delete()

    @less_console_noise_decorator
    def test_created_on_display(self):
        """Tests the custom created on which is a reskin of the created_at field"""
        created_on = self.admin.created_on(self.portfolio)
        expected_date = self.portfolio.created_at.strftime("%b %d, %Y")
        self.assertEqual(created_on, expected_date)

    @less_console_noise_decorator
    def test_suborganizations_display(self):
        """Tests the custom suborg field which displays all related suborgs"""
        Suborganization.objects.create(name="Sub1", portfolio=self.portfolio)
        Suborganization.objects.create(name="Sub2", portfolio=self.portfolio)

        suborganizations = self.admin.suborganizations(self.portfolio)
        self.assertIn("Sub1", suborganizations)
        self.assertIn("Sub2", suborganizations)
        self.assertIn('<ul class="add-list-reset">', suborganizations)

    @less_console_noise_decorator
    def test_domains_display(self):
        """Tests the custom domains field which displays all related domains"""
        request_1 = completed_domain_request(
            name="request1.gov", portfolio=self.portfolio, status=DomainRequest.DomainRequestStatus.IN_REVIEW
        )
        request_2 = completed_domain_request(
            name="request2.gov", portfolio=self.portfolio, status=DomainRequest.DomainRequestStatus.IN_REVIEW
        )

        # Create some domain objects
        request_1.approve()
        request_2.approve()

        domain_1 = DomainInformation.objects.get(domain_request=request_1).domain
        domain_1.name = "domain1.gov"
        domain_1.save()
        domain_2 = DomainInformation.objects.get(domain_request=request_2).domain
        domain_2.name = "domain2.gov"
        domain_2.save()

        domains = self.admin.domains(self.portfolio)
        self.assertIn("2 domains", domains)

    @less_console_noise_decorator
    def test_domain_requests_display(self):
        """Tests the custom domains requests field which displays all related requests"""
        completed_domain_request(name="request1.gov", portfolio=self.portfolio)
        completed_domain_request(name="request2.gov", portfolio=self.portfolio)

        domain_requests = self.admin.domain_requests(self.portfolio)
        self.assertIn("2 domain requests", domain_requests)

    @less_console_noise_decorator
    def test_portfolio_members_display(self):
        """Tests the custom portfolio members field, admin and member sections"""
        admin_user_1 = User.objects.create(
            username="testuser1",
            first_name="Gerald",
            last_name="Meoward",
            title="Captain",
            email="meaoward@gov.gov",
        )

        UserPortfolioPermission.objects.all().create(
            user=admin_user_1, portfolio=self.portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )

        admin_user_2 = User.objects.create(
            username="testuser2",
            first_name="Arnold",
            last_name="Poopy",
            title="Major",
            email="poopy@gov.gov",
        )

        UserPortfolioPermission.objects.all().create(
            user=admin_user_2, portfolio=self.portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
        )

        admin_user_3 = User.objects.create(
            username="testuser3",
            first_name="Mad",
            last_name="Max",
            title="Road warrior",
            email="madmax@gov.gov",
        )

        UserPortfolioPermission.objects.all().create(
            user=admin_user_3, portfolio=self.portfolio, roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER]
        )

        admin_user_4 = User.objects.create(
            username="testuser4",
            first_name="Agent",
            last_name="Smith",
            title="Program",
            email="thematrix@gov.gov",
        )

        UserPortfolioPermission.objects.all().create(
            user=admin_user_4,
            portfolio=self.portfolio,
            additional_permissions=[
                UserPortfolioPermissionChoices.VIEW_PORTFOLIO,
                UserPortfolioPermissionChoices.EDIT_REQUESTS,
            ],
        )

        display_admins = self.admin.display_admins(self.portfolio)

        self.assertIn(
            f'<a href="/admin/registrar/user/{admin_user_1.pk}/change/">Gerald Meoward meaoward@gov.gov</a>',
            display_admins,
        )
        self.assertIn("Captain", display_admins)
        self.assertIn(
            f'<a href="/admin/registrar/user/{admin_user_2.pk}/change/">Arnold Poopy poopy@gov.gov</a>', display_admins
        )
        self.assertIn("Major", display_admins)

        display_members_summary = self.admin.display_members_summary(self.portfolio)

        self.assertIn(
            f'<a href="/admin/registrar/user/{admin_user_3.pk}/change/">Mad Max madmax@gov.gov</a>',
            display_members_summary,
        )
        self.assertIn(
            f'<a href="/admin/registrar/user/{admin_user_4.pk}/change/">Agent Smith thematrix@gov.gov</a>',
            display_members_summary,
        )

        display_members = self.admin.display_members(self.portfolio)

        self.assertIn("Mad Max", display_members)
        self.assertIn("<span class='usa-tag'>Member</span>", display_members)
        self.assertIn("Road warrior", display_members)
        self.assertIn("Agent Smith", display_members)
        self.assertIn("<span class='usa-tag'>Domain requestor</span>", display_members)
        self.assertIn("Program", display_members)
