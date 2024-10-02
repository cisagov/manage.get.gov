from django.urls import reverse

from registrar.models.portfolio import Portfolio
from registrar.models.user import User
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices
from .test_views import TestWithUser
from django_webtest import WebTest  # type: ignore


class GetPortfolioMembersJsonTest(TestWithUser, WebTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create additional users
        cls.user2 = User.objects.create(
            username="test_user2",
            first_name="Second",
            last_name="User",
            email="second@example.com",
            phone="8003112345",
            title="Member",
        )
        cls.user3 = User.objects.create(
            username="test_user3",
            first_name="Third",
            last_name="User",
            email="third@example.com",
            phone="8003113456",
            title="Member",
        )
        cls.user4 = User.objects.create(
            username="test_user4",
            first_name="Fourth",
            last_name="User",
            email="fourth@example.com",
            phone="8003114567",
            title="Admin",
        )

        # Create Portfolio
        cls.portfolio = Portfolio.objects.create(creator=cls.user, organization_name="Test Portfolio")

        # Assign permissions
        UserPortfolioPermission.objects.create(
            user=cls.user,
            portfolio=cls.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
            additional_permissions=[
                UserPortfolioPermissionChoices.VIEW_MEMBERS,
                UserPortfolioPermissionChoices.EDIT_MEMBERS,
            ],
        )
        UserPortfolioPermission.objects.create(
            user=cls.user2,
            portfolio=cls.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
        )
        UserPortfolioPermission.objects.create(
            user=cls.user3,
            portfolio=cls.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
        )
        UserPortfolioPermission.objects.create(
            user=cls.user4,
            portfolio=cls.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
        )

    def setUp(self):
        super().setUp()
        self.app.set_user(self.user.username)

    def test_get_portfolio_members_json_authenticated(self):
        """Test that portfolio members are returned properly for an authenticated user."""
        response = self.app.get(reverse("get_portfolio_members_json"), params={"portfolio": self.portfolio.id})
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_previous"])
        self.assertFalse(data["has_next"])
        self.assertEqual(data["num_pages"], 1)
        self.assertEqual(data["total"], 4)
        self.assertEqual(data["unfiltered_total"], 4)

        # Check the number of members
        self.assertEqual(len(data["members"]), 4)

        # Check member fields
        expected_emails = {self.user.email, self.user2.email, self.user3.email, self.user4.email}
        actual_emails = {member["email"] for member in data["members"]}
        self.assertEqual(expected_emails, actual_emails)

    def test_pagination(self):
        """Test that pagination works properly when there are more members than page size."""
        # Create additional members to exceed page size of 10
        for i in range(5, 15):
            user, _ = User.objects.get_or_create(
                username=f"test_user{i}",
                first_name=f"User{i}",
                last_name=f"Last{i}",
                email=f"user{i}@example.com",
                phone=f"80031156{i}",
                title="Member",
            )
            UserPortfolioPermission.objects.create(
                user=user,
                portfolio=self.portfolio,
                roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            )

        response = self.app.get(
            reverse("get_portfolio_members_json"), params={"portfolio": self.portfolio.id, "page": 1}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertTrue(data["has_next"])
        self.assertFalse(data["has_previous"])
        self.assertEqual(data["num_pages"], 2)
        self.assertEqual(data["total"], 14)
        self.assertEqual(data["unfiltered_total"], 14)

        # Check the number of members on page 1
        self.assertEqual(len(data["members"]), 10)

        response = self.app.get(
            reverse("get_portfolio_members_json"), params={"portfolio": self.portfolio.id, "page": 2}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info for page 2
        self.assertEqual(data["page"], 2)
        self.assertFalse(data["has_next"])
        self.assertTrue(data["has_previous"])
        self.assertEqual(data["num_pages"], 2)

        # Check the number of members on page 2
        self.assertEqual(len(data["members"]), 4)

    def test_search(self):
        """Test search functionality for portfolio members."""
        # Search by first name
        response = self.app.get(
            reverse("get_portfolio_members_json"), params={"portfolio": self.portfolio.id, "search_term": "Second"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(len(data["members"]), 1)
        self.assertEqual(data["members"][0]["first_name"], "Second")
        self.assertEqual(data["members"][0]["email"], "second@example.com")

        # Search by last name
        response = self.app.get(
            reverse("get_portfolio_members_json"), params={"portfolio": self.portfolio.id, "search_term": "Last3"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(len(data["members"]), 1)
        self.assertEqual(data["members"][0]["last_name"], "User")

        # Search by email
        response = self.app.get(
            reverse("get_portfolio_members_json"),
            params={"portfolio": self.portfolio.id, "search_term": "fourth@example.com"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(len(data["members"]), 1)
        self.assertEqual(data["members"][0]["email"], "fourth@example.com")

        # Search with no matching results
        response = self.app.get(
            reverse("get_portfolio_members_json"), params={"portfolio": self.portfolio.id, "search_term": "NonExistent"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(len(data["members"]), 0)
