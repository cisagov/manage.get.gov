from django.urls import reverse

from api.tests.common import less_console_noise_decorator
from registrar.models.domain import Domain
from registrar.models.domain_information import DomainInformation
from registrar.models.domain_invitation import DomainInvitation
from registrar.models.portfolio import Portfolio
from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.user import User
from registrar.models.user_domain_role import UserDomainRole
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices
from .test_views import TestWithUser
from django_webtest import WebTest  # type: ignore


class GetPortfolioMemberDomainsJsonTest(TestWithUser, WebTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test member
        cls.user_member = User.objects.create(
            username="test_member",
            first_name="Second",
            last_name="User",
            email="second@example.com",
            phone="8003112345",
            title="Member",
        )

        # Create test user with no perms
        cls.user_no_perms = User.objects.create(
            username="test_user_no_perms",
            first_name="No",
            last_name="Permissions",
            email="user_no_perms@example.com",
            phone="8003112345",
            title="No Permissions",
        )

        # Create Portfolio
        cls.portfolio = Portfolio.objects.create(requester=cls.user, organization_name="Test Portfolio")

        # Assign permissions to the user making requests
        UserPortfolioPermission.objects.create(
            user=cls.user,
            portfolio=cls.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            additional_permissions=[
                UserPortfolioPermissionChoices.VIEW_MEMBERS,
                UserPortfolioPermissionChoices.EDIT_MEMBERS,
            ],
        )

        # Assign some domains
        cls.domain1 = Domain.objects.create(name="example1.com", expiration_date="2024-03-01", state="ready")
        cls.domain2 = Domain.objects.create(name="example2.com", expiration_date="2024-03-01", state="ready")
        cls.domain3 = Domain.objects.create(name="example3.com", expiration_date="2024-03-01", state="ready")
        cls.domain4 = Domain.objects.create(name="example4.com", expiration_date="2024-03-01", state="ready")

        # Add domain1 and domain2 to portfolio
        DomainInformation.objects.create(requester=cls.user, domain=cls.domain1, portfolio=cls.portfolio)
        DomainInformation.objects.create(requester=cls.user, domain=cls.domain2, portfolio=cls.portfolio)
        DomainInformation.objects.create(requester=cls.user, domain=cls.domain3, portfolio=cls.portfolio)
        DomainInformation.objects.create(requester=cls.user, domain=cls.domain4, portfolio=cls.portfolio)

        # Assign user_member to view all domains
        UserPortfolioPermission.objects.create(
            user=cls.user_member,
            portfolio=cls.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
        )
        # Add user_member as manager of domains
        UserDomainRole.objects.create(user=cls.user_member, domain=cls.domain1, role=UserDomainRole.Roles.MANAGER)
        UserDomainRole.objects.create(user=cls.user_member, domain=cls.domain2, role=UserDomainRole.Roles.MANAGER)
        UserDomainRole.objects.create(user=cls.user_member, domain=cls.domain3, role=UserDomainRole.Roles.MANAGER)
        UserDomainRole.objects.create(user=cls.user_no_perms, domain=cls.domain3, role=UserDomainRole.Roles.MANAGER)

        # Add an invited member who has been invited to manage domains
        cls.invited_member_email = "invited@example.com"
        PortfolioInvitation.objects.create(
            email=cls.invited_member_email,
            portfolio=cls.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            additional_permissions=[
                UserPortfolioPermissionChoices.VIEW_MEMBERS,
            ],
        )
        DomainInvitation.objects.create(
            email=cls.invited_member_email, domain=cls.domain1, status=DomainInvitation.DomainInvitationStatus.INVITED
        )
        DomainInvitation.objects.create(
            email=cls.invited_member_email, domain=cls.domain2, status=DomainInvitation.DomainInvitationStatus.INVITED
        )
        DomainInvitation.objects.create(
            email=cls.invited_member_email, domain=cls.domain3, status=DomainInvitation.DomainInvitationStatus.CANCELED
        )
        DomainInvitation.objects.create(
            email=cls.invited_member_email, domain=cls.domain4, status=DomainInvitation.DomainInvitationStatus.RETRIEVED
        )

    @classmethod
    def tearDownClass(cls):
        PortfolioInvitation.objects.all().delete()
        UserPortfolioPermission.objects.all().delete()
        UserDomainRole.objects.all().delete()
        DomainInvitation.objects.all().delete()
        DomainInformation.objects.all().delete()
        Domain.objects.all().delete()
        Portfolio.objects.all().delete()
        User.objects.all().delete()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.app.set_user(self.user.username)

    @less_console_noise_decorator
    def test_get_portfolio_member_domains_json_authenticated(self):
        """Test that portfolio member's domains are returned properly for an authenticated user."""
        response = self.app.get(
            reverse("get_member_domains_json"),
            params={"portfolio": self.portfolio.id, "member_id": self.user_member.id, "member_only": "true"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_previous"])
        self.assertFalse(data["has_next"])
        self.assertEqual(data["num_pages"], 1)
        self.assertEqual(data["total"], 3)
        self.assertEqual(data["unfiltered_total"], 3)

        # Check the number of domains
        self.assertEqual(len(data["domains"]), 3)

    @less_console_noise_decorator
    def test_get_portfolio_invitedmember_domains_json_authenticated(self):
        """Test that portfolio invitedmember's domains are returned properly for an authenticated user.
        CANCELED and RETRIEVED invites should be ignored."""
        response = self.app.get(
            reverse("get_member_domains_json"),
            params={"portfolio": self.portfolio.id, "email": self.invited_member_email, "member_only": "true"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_previous"])
        self.assertFalse(data["has_next"])
        self.assertEqual(data["num_pages"], 1)
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["unfiltered_total"], 2)

        # Check the number of domains
        self.assertEqual(len(data["domains"]), 2)

    @less_console_noise_decorator
    def test_get_portfolio_member_domains_json_authenticated_include_all_domains(self):
        """Test that all portfolio domains are returned properly for an authenticated user."""
        response = self.app.get(
            reverse("get_member_domains_json"),
            params={"portfolio": self.portfolio.id, "member_id": self.user_member.id, "member_only": "false"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_previous"])
        self.assertFalse(data["has_next"])
        self.assertEqual(data["num_pages"], 1)
        self.assertEqual(data["total"], 4)
        self.assertEqual(data["unfiltered_total"], 4)

        # Check the number of domains
        self.assertEqual(len(data["domains"]), 4)

    @less_console_noise_decorator
    def test_get_portfolio_invitedmember_domains_json_authenticated_include_all_domains(self):
        """Test that all portfolio domains are returned properly for an authenticated user."""
        response = self.app.get(
            reverse("get_member_domains_json"),
            params={"portfolio": self.portfolio.id, "email": self.invited_member_email, "member_only": "false"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_previous"])
        self.assertFalse(data["has_next"])
        self.assertEqual(data["num_pages"], 1)
        self.assertEqual(data["total"], 4)
        self.assertEqual(data["unfiltered_total"], 4)

        # Check the number of domains
        self.assertEqual(len(data["domains"]), 4)

    @less_console_noise_decorator
    def test_get_portfolio_member_domains_json_authenticated_search(self):
        """Test that search_term yields correct domain."""
        response = self.app.get(
            reverse("get_member_domains_json"),
            params={
                "portfolio": self.portfolio.id,
                "member_id": self.user_member.id,
                "member_only": "false",
                "search_term": "example1",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_previous"])
        self.assertFalse(data["has_next"])
        self.assertEqual(data["num_pages"], 1)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["unfiltered_total"], 4)

        # Check the number of domains
        self.assertEqual(len(data["domains"]), 1)

    @less_console_noise_decorator
    def test_get_portfolio_invitedmember_domains_json_authenticated_search(self):
        """Test that search_term yields correct domain."""
        response = self.app.get(
            reverse("get_member_domains_json"),
            params={
                "portfolio": self.portfolio.id,
                "email": self.invited_member_email,
                "member_only": "false",
                "search_term": "example1",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_previous"])
        self.assertFalse(data["has_next"])
        self.assertEqual(data["num_pages"], 1)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["unfiltered_total"], 4)

        # Check the number of domains
        self.assertEqual(len(data["domains"]), 1)

    @less_console_noise_decorator
    def test_get_portfolio_member_domains_json_authenticated_sort(self):
        """Test that sort returns results in correct order."""
        # Test by name in ascending order
        response = self.app.get(
            reverse("get_member_domains_json"),
            params={
                "portfolio": self.portfolio.id,
                "member_id": self.user_member.id,
                "member_only": "false",
                "sort_by": "name",
                "order": "asc",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_previous"])
        self.assertFalse(data["has_next"])
        self.assertEqual(data["num_pages"], 1)
        self.assertEqual(data["total"], 4)
        self.assertEqual(data["unfiltered_total"], 4)

        # Check the number of domains
        self.assertEqual(len(data["domains"]), 4)

        # Check the name of the first domain is example1.com
        self.assertEqual(data["domains"][0]["name"], "example1.com")

        # Test by name in descending order
        response = self.app.get(
            reverse("get_member_domains_json"),
            params={
                "portfolio": self.portfolio.id,
                "member_id": self.user_member.id,
                "member_only": "false",
                "sort_by": "name",
                "order": "desc",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_previous"])
        self.assertFalse(data["has_next"])
        self.assertEqual(data["num_pages"], 1)
        self.assertEqual(data["total"], 4)
        self.assertEqual(data["unfiltered_total"], 4)

        # Check the number of domains
        self.assertEqual(len(data["domains"]), 4)

        # Check the name of the first domain is example1.com
        self.assertEqual(data["domains"][0]["name"], "example4.com")

    @less_console_noise_decorator
    def test_get_portfolio_member_domains_json_authenticated_sort_by_checked(self):
        """Test that sort returns results in correct order."""
        # Test by checked in ascending order
        response = self.app.get(
            reverse("get_member_domains_json"),
            params={
                "portfolio": self.portfolio.id,
                "email": self.user_member.id,
                "member_only": "false",
                "checkedDomainIds": f"{self.domain2.id},{self.domain3.id}",
                "sort_by": "checked",
                "order": "asc",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_previous"])
        self.assertFalse(data["has_next"])
        self.assertEqual(data["num_pages"], 1)
        self.assertEqual(data["total"], 4)
        self.assertEqual(data["unfiltered_total"], 4)

        # Check the number of domains
        self.assertEqual(len(data["domains"]), 4)

        # Check the name of the first domain is the first unchecked domain sorted alphabetically
        self.assertEqual(data["domains"][0]["name"], "example1.com")
        self.assertEqual(data["domains"][1]["name"], "example4.com")

        # Test by checked in descending order
        response = self.app.get(
            reverse("get_member_domains_json"),
            params={
                "portfolio": self.portfolio.id,
                "email": self.user_member.id,
                "member_only": "false",
                "checkedDomainIds": f"{self.domain2.id},{self.domain3.id}",
                "sort_by": "checked",
                "order": "desc",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_previous"])
        self.assertFalse(data["has_next"])
        self.assertEqual(data["num_pages"], 1)
        self.assertEqual(data["total"], 4)
        self.assertEqual(data["unfiltered_total"], 4)

        # Check the number of domains
        self.assertEqual(len(data["domains"]), 4)

        # Check the name of the first domain is the first checked domain sorted alphabetically
        self.assertEqual(data["domains"][0]["name"], "example2.com")
        self.assertEqual(data["domains"][1]["name"], "example3.com")

    @less_console_noise_decorator
    def test_get_portfolio_member_domains_json_authenticated_member_is_only_manager(self):
        """Test that sort returns member_is_only_manager when member_domain_role_exists
        and member_domain_role_count == 1"""
        response = self.app.get(
            reverse("get_member_domains_json"),
            params={
                "portfolio": self.portfolio.id,
                "member_id": self.user_member.id,
                "member_only": "false",
                "sort_by": "name",
                "order": "asc",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_previous"])
        self.assertFalse(data["has_next"])
        self.assertEqual(data["num_pages"], 1)
        self.assertEqual(data["total"], 4)
        self.assertEqual(data["unfiltered_total"], 4)

        # Check the number of domains
        self.assertEqual(len(data["domains"]), 4)

        self.assertEqual(data["domains"][0]["name"], "example1.com")
        self.assertEqual(data["domains"][1]["name"], "example2.com")
        self.assertEqual(data["domains"][2]["name"], "example3.com")
        self.assertEqual(data["domains"][3]["name"], "example4.com")

        self.assertEqual(data["domains"][0]["member_is_only_manager"], True)
        self.assertEqual(data["domains"][1]["member_is_only_manager"], True)
        # domain3 has 2 managers
        self.assertEqual(data["domains"][2]["member_is_only_manager"], False)
        # no managers on this one
        self.assertEqual(data["domains"][3]["member_is_only_manager"], False)

    @less_console_noise_decorator
    def test_get_portfolio_invitedmember_domains_json_authenticated_sort(self):
        """Test that sort returns results in correct order."""
        # Test by name in ascending order
        response = self.app.get(
            reverse("get_member_domains_json"),
            params={
                "portfolio": self.portfolio.id,
                "email": self.invited_member_email,
                "member_only": "false",
                "sort_by": "name",
                "order": "asc",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_previous"])
        self.assertFalse(data["has_next"])
        self.assertEqual(data["num_pages"], 1)
        self.assertEqual(data["total"], 4)
        self.assertEqual(data["unfiltered_total"], 4)

        # Check the number of domains
        self.assertEqual(len(data["domains"]), 4)

        # Check the name of the first domain is example1.com
        self.assertEqual(data["domains"][0]["name"], "example1.com")

        # Test by name in descending order
        response = self.app.get(
            reverse("get_member_domains_json"),
            params={
                "portfolio": self.portfolio.id,
                "email": self.invited_member_email,
                "member_only": "false",
                "sort_by": "name",
                "order": "desc",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_previous"])
        self.assertFalse(data["has_next"])
        self.assertEqual(data["num_pages"], 1)
        self.assertEqual(data["total"], 4)
        self.assertEqual(data["unfiltered_total"], 4)

        # Check the number of domains
        self.assertEqual(len(data["domains"]), 4)

        # Check the name of the first domain is example1.com
        self.assertEqual(data["domains"][0]["name"], "example4.com")

    @less_console_noise_decorator
    def test_get_portfolio_invitedmember_domains_json_authenticated_sort_by_checked(self):
        """Test that sort returns results in correct order."""
        # Test by checked in ascending order
        response = self.app.get(
            reverse("get_member_domains_json"),
            params={
                "portfolio": self.portfolio.id,
                "email": self.invited_member_email,
                "member_only": "false",
                "checkedDomainIds": f"{self.domain2.id},{self.domain3.id}",
                "sort_by": "checked",
                "order": "asc",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_previous"])
        self.assertFalse(data["has_next"])
        self.assertEqual(data["num_pages"], 1)
        self.assertEqual(data["total"], 4)
        self.assertEqual(data["unfiltered_total"], 4)

        # Check the number of domains
        self.assertEqual(len(data["domains"]), 4)

        # Check the name of the first domain is the first unchecked domain sorted alphabetically
        self.assertEqual(data["domains"][0]["name"], "example1.com")
        self.assertEqual(data["domains"][1]["name"], "example4.com")

        # Test by checked in descending order
        response = self.app.get(
            reverse("get_member_domains_json"),
            params={
                "portfolio": self.portfolio.id,
                "email": self.invited_member_email,
                "member_only": "false",
                "checkedDomainIds": f"{self.domain2.id},{self.domain3.id}",
                "sort_by": "checked",
                "order": "desc",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_previous"])
        self.assertFalse(data["has_next"])
        self.assertEqual(data["num_pages"], 1)
        self.assertEqual(data["total"], 4)
        self.assertEqual(data["unfiltered_total"], 4)

        # Check the number of domains
        self.assertEqual(len(data["domains"]), 4)

        # Check the name of the first domain is the first checked domain sorted alphabetically
        self.assertEqual(data["domains"][0]["name"], "example2.com")
        self.assertEqual(data["domains"][1]["name"], "example3.com")

    @less_console_noise_decorator
    def test_get_portfolio_members_json_restricted_user(self):
        """Test that an restricted user is denied access."""
        # set user to a user with no permissions
        self.app.set_user(self.user_no_perms)

        # Try to access the portfolio members without being authenticated
        response = self.app.get(
            reverse("get_member_domains_json"),
            params={"portfolio": self.portfolio.id, "member_id": self.user_member.id, "member_only": "true"},
            expect_errors=True,
        )

        # Assert that the response is a 403
        self.assertEqual(response.status_code, 403)

    @less_console_noise_decorator
    def test_get_portfolio_members_json_unauthenticated(self):
        """Test that an unauthenticated user is redirected to login."""
        # set app to unauthenticated
        self.app.set_user(None)

        # Try to access the portfolio members without being authenticated
        response = self.app.get(
            reverse("get_member_domains_json"),
            params={"portfolio": self.portfolio.id, "member_id": self.user_member.id, "member_only": "true"},
            expect_errors=True,
        )

        # Assert that the response is a redirect to openid login
        self.assertEqual(response.status_code, 302)
        self.assertIn("/openid/login", response.location)
