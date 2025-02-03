from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, Client
from api.tests.common import less_console_noise_decorator
from django.urls import reverse
from django_webtest import WebTest  # type: ignore
from registrar.admin import (
    DomainAdmin,
)
from registrar.models import Domain, DomainInvitation, User, Host, DomainInformation, UserDomainRole
from .common import create_superuser, MockEppLib, GenericTestHelper


class TestUserDomainRoleAsStaff(MockEppLib, WebTest):
    """Test UserDomainRole class as staff user.

    Notes:
      all tests share staffuser; do not change staffuser model in tests
      tests have available staffuser, client, and admin
    """

    # csrf checks do not work with WebTest.
    # We disable them here. TODO for another ticket.
    csrf_checks = False

    @classmethod
    def setUpClass(self):
        super().setUpClass()
        self.site = AdminSite()
        self.admin = DomainAdmin(model=DomainInvitation, admin_site=self.site)
        self.factory = RequestFactory()
        self.superuser = create_superuser()

    def setUp(self):
        self.client = Client(HTTP_HOST="localhost:8080")
        self.client.force_login(self.superuser)
        super().setUp()
        self.app.set_user(self.superuser.username)

    def tearDown(self):
        super().tearDown()
        UserDomainRole.objects.all().delete()
        DomainInformation.objects.all().delete()
        Host.objects.all().delete()
        DomainInvitation.objects.all().delete()

    @classmethod
    def tearDownClass(self):
        User.objects.all().delete()
        super().tearDownClass()

    @less_console_noise_decorator
    def test_custom_delete_confirmation_page(self):
        """Tests if custom alerts display on User Domain Role delete page"""
        domain, _ = Domain.objects.get_or_create(name="user-domain-role-test.gov", state=Domain.State.READY)
        domain_role, _ = UserDomainRole.objects.get_or_create(domain=domain, user=self.superuser)

        domain_invitation_change_page = self.app.get(
            reverse("admin:registrar_userdomainrole_change", args=[domain_role.pk])
        )

        self.assertContains(domain_invitation_change_page, "user-domain-role-test.gov")
        # click the "Delete" link
        confirmation_page = domain_invitation_change_page.click("Delete", index=0)

        custom_alert_content = "If you remove someone from a domain here"
        self.assertContains(confirmation_page, custom_alert_content)

    @less_console_noise_decorator
    def test_custom_selected_delete_confirmation_page(self):
        """Tests if custom alerts display on selected delete page from User Domain Roles table"""
        domain, _ = Domain.objects.get_or_create(name="domain-invitation-test.gov", state=Domain.State.READY)
        domain_role, _ = UserDomainRole.objects.get_or_create(domain=domain, user=self.superuser)

        # Get the index. The post expects the index to be encoded as a string
        index = f"{domain_role.id}"

        test_helper = GenericTestHelper(
            factory=self.factory,
            user=self.superuser,
            admin=self.admin,
            url=reverse("admin:registrar_userdomainrole_changelist"),
            model=Domain,
            client=self.client,
        )

        # Simulate selecting a single record, then clicking "Delete selected domains"
        response = test_helper.get_table_delete_confirmation_page("0", index)

        # Check for custom alert message
        custom_alert_content = "If you remove someone from a domain here"
        self.assertContains(response, custom_alert_content)
