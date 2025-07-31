from registrar.models import DomainRequest
from django.urls import reverse

from registrar.models.draft_domain import DraftDomain
from registrar.models.portfolio import Portfolio
from registrar.models.user import User
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices
from .test_views import TestWithUser
from django_webtest import WebTest  # type: ignore
from django.utils.dateparse import parse_datetime


class GetRequestsJsonTest(TestWithUser, WebTest):
    def setUp(self):
        super().setUp()
        self.app.set_user(self.user.username)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        lamb_chops, _ = DraftDomain.objects.get_or_create(name="lamb-chops.gov")
        short_ribs, _ = DraftDomain.objects.get_or_create(name="short-ribs.gov")
        beef_chuck, _ = DraftDomain.objects.get_or_create(name="beef-chuck.gov")
        stew_beef, _ = DraftDomain.objects.get_or_create(name="stew-beef.gov")

        # Create Portfolio
        cls.portfolio = Portfolio.objects.create(creator=cls.user, organization_name="Example org")

        # create a second user to assign requests to
        cls.user2 = User.objects.create(
            username="test_user2",
            first_name="Second",
            last_name="last",
            email="info2@example.com",
            phone="8003111234",
            title="title",
        )

        # Create domain requests for the user
        cls.domain_requests = [
            DomainRequest.objects.create(
                creator=cls.user,
                requested_domain=lamb_chops,
                last_submitted_date="2024-01-01",
                status=DomainRequest.DomainRequestStatus.STARTED,
                created_at="2024-01-01",
                portfolio=cls.portfolio,
            ),
            DomainRequest.objects.create(
                creator=cls.user,
                requested_domain=short_ribs,
                last_submitted_date="2024-02-01",
                status=DomainRequest.DomainRequestStatus.WITHDRAWN,
                created_at="2024-02-01",
            ),
            DomainRequest.objects.create(
                creator=cls.user,
                requested_domain=beef_chuck,
                last_submitted_date="2024-03-01",
                status=DomainRequest.DomainRequestStatus.REJECTED,
                created_at="2024-03-01",
                portfolio=cls.portfolio,
            ),
            DomainRequest.objects.create(
                creator=cls.user,
                requested_domain=stew_beef,
                last_submitted_date="2024-04-01",
                status=DomainRequest.DomainRequestStatus.STARTED,
                created_at="2024-04-01",
            ),
            DomainRequest.objects.create(
                creator=cls.user,
                requested_domain=None,
                last_submitted_date="2024-05-01",
                status=DomainRequest.DomainRequestStatus.STARTED,
                created_at="2024-05-01",
            ),
            DomainRequest.objects.create(
                creator=cls.user,
                requested_domain=None,
                last_submitted_date="2024-06-01",
                status=DomainRequest.DomainRequestStatus.WITHDRAWN,
                created_at="2024-06-01",
            ),
            DomainRequest.objects.create(
                creator=cls.user,
                requested_domain=None,
                last_submitted_date="2024-07-01",
                status=DomainRequest.DomainRequestStatus.REJECTED,
                created_at="2024-07-01",
            ),
            DomainRequest.objects.create(
                creator=cls.user,
                requested_domain=None,
                last_submitted_date="2024-08-01",
                status=DomainRequest.DomainRequestStatus.STARTED,
                created_at="2024-08-01",
            ),
            DomainRequest.objects.create(
                creator=cls.user,
                requested_domain=None,
                last_submitted_date="2024-09-01",
                status=DomainRequest.DomainRequestStatus.STARTED,
                created_at="2024-09-01",
            ),
            DomainRequest.objects.create(
                creator=cls.user,
                requested_domain=None,
                last_submitted_date="2024-10-01",
                status=DomainRequest.DomainRequestStatus.WITHDRAWN,
                created_at="2024-10-01",
            ),
            DomainRequest.objects.create(
                creator=cls.user,
                requested_domain=None,
                last_submitted_date="2024-11-01",
                status=DomainRequest.DomainRequestStatus.REJECTED,
                created_at="2024-11-01",
            ),
            DomainRequest.objects.create(
                creator=cls.user,
                requested_domain=None,
                last_submitted_date="2024-11-02",
                status=DomainRequest.DomainRequestStatus.WITHDRAWN,
                created_at="2024-11-02",
            ),
            DomainRequest.objects.create(
                creator=cls.user,
                requested_domain=None,
                last_submitted_date="2024-12-01",
                status=DomainRequest.DomainRequestStatus.APPROVED,
                created_at="2024-12-01",
            ),
            DomainRequest.objects.create(
                creator=cls.user2,
                requested_domain=None,
                last_submitted_date="2024-12-01",
                status=DomainRequest.DomainRequestStatus.STARTED,
                created_at="2024-12-01",
                portfolio=cls.portfolio,
            ),
        ]

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        DomainRequest.objects.all().delete()
        DraftDomain.objects.all().delete()
        Portfolio.objects.all().delete()

    def test_get_domain_requests_json_authenticated(self):
        """Test that domain requests are returned properly for an authenticated user."""
        deletable_statuses = [
            DomainRequest.DomainRequestStatus.STARTED,
            DomainRequest.DomainRequestStatus.WITHDRAWN,
        ]

        editable_statuses = [
            DomainRequest.DomainRequestStatus.STARTED,
            DomainRequest.DomainRequestStatus.ACTION_NEEDED,
            DomainRequest.DomainRequestStatus.WITHDRAWN,
        ]

        view_only_statuses = [
            DomainRequest.DomainRequestStatus.REJECTED,
        ]

        response = self.app.get(reverse("get_domain_requests_json"))
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertTrue(data["has_next"])
        self.assertFalse(data["has_previous"])
        self.assertEqual(data["num_pages"], 2)

        # Check the number of domain requests
        self.assertEqual(len(data["domain_requests"]), 10)

        # Extract fields from response
        requested_domains = [request["requested_domain"] for request in data["domain_requests"]]
        last_submitted_dates = [request["last_submitted_date"] for request in data["domain_requests"]]
        statuses = [request["status"] for request in data["domain_requests"]]
        created_ats = [request["created_at"] for request in data["domain_requests"]]
        ids = [request["id"] for request in data["domain_requests"]]
        is_deletables = [request["is_deletable"] for request in data["domain_requests"]]
        action_urls = [request["action_url"] for request in data["domain_requests"]]
        action_labels = [request["action_label"] for request in data["domain_requests"]]
        svg_icons = [request["svg_icon"] for request in data["domain_requests"]]

        # Check fields for each domain request
        for i in range(10):
            self.assertNotEqual(data["domain_requests"][i]["status"], "Approved")
            self.assertEqual(
                self.domain_requests[i].requested_domain.name if self.domain_requests[i].requested_domain else None,
                requested_domains[i],
            )
            self.assertEqual(self.domain_requests[i].last_submitted_date, last_submitted_dates[i])
            self.assertEqual(self.domain_requests[i].get_status_display(), statuses[i])
            self.assertEqual(
                parse_datetime(self.domain_requests[i].created_at.isoformat()), parse_datetime(created_ats[i])
            )
            self.assertEqual(self.domain_requests[i].id, ids[i])

            # Check is_deletable
            is_deletable_expected = self.domain_requests[i].status in deletable_statuses
            self.assertEqual(is_deletable_expected, is_deletables[i])

            # Check action_url
            if self.domain_requests[i].status in view_only_statuses:
                action_url_expected = reverse(
                    "domain-request-status-viewonly", kwargs={"domain_request_pk": self.domain_requests[i].id}
                )
                action_label_expected = "View"
                svg_icon_expected = "visibility"
            elif self.domain_requests[i].status in editable_statuses:
                action_url_expected = reverse(
                    "edit-domain-request", kwargs={"domain_request_pk": self.domain_requests[i].id}
                )
                action_label_expected = "Edit"
                svg_icon_expected = "edit"
            else:
                action_url_expected = reverse(
                    "domain-request-status", kwargs={"domain_request_pk": self.domain_requests[i].id}
                )
                action_label_expected = "Manage"
                svg_icon_expected = "settings"

            self.assertEqual(action_url_expected, action_urls[i])
            self.assertEqual(action_label_expected, action_labels[i])
            self.assertEqual(svg_icon_expected, svg_icons[i])

    def test_get_domain_requests_json_search(self):
        """Test search."""
        # Define your URL variables as a dictionary
        url_vars = {"search_term": "lamb"}

        # Use the params parameter to include URL variables
        response = self.app.get(reverse("get_domain_requests_json"), params=url_vars)
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_next"])
        self.assertFalse(data["has_previous"])
        self.assertEqual(data["num_pages"], 1)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["unfiltered_total"], 12)

        # Check the number of domain requests
        self.assertEqual(len(data["domain_requests"]), 1)

        # Extract fields from response
        requested_domains = [request["requested_domain"] for request in data["domain_requests"]]

        self.assertEqual(
            self.domain_requests[0].requested_domain.name,
            requested_domains[0],
        )

    def test_get_domain_requests_json_search_new_domains(self):
        """Test search when looking up New domain requests"""
        # Define your URL variables as a dictionary
        url_vars = {"search_term": "ew"}

        # Use the params parameter to include URL variables
        response = self.app.get(reverse("get_domain_requests_json"), params=url_vars)
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        pagination_fields = ["page", "has_next", "has_previous", "num_pages", "total", "unfiltered_total"]
        expected_pagination_values = [1, False, False, 1, 9, 12]
        for field, expected_value in zip(pagination_fields, expected_pagination_values):
            self.assertEqual(data[field], expected_value)

        # Check the number of domain requests
        self.assertEqual(len(data["domain_requests"]), 9)

        # Extract fields from response
        requested_domains = [request.get("requested_domain") for request in data["domain_requests"]]

        expected_domain_values = ["stew-beef.gov"] + [None] * 8
        for expected_value, actual_value in zip(expected_domain_values, requested_domains):
            self.assertEqual(expected_value, actual_value)

    def test_get_domain_requests_json_with_portfolio_view_all_requests(self):
        """Test that an authenticated user gets the list of 3 requests for portfolio. The 3 requests
        are the requests that are associated with the portfolio."""

        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            additional_permissions=[UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS],
        )

        response = self.app.get(reverse("get_domain_requests_json"), {"portfolio": self.portfolio.id})
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_next"])
        self.assertFalse(data["has_previous"])
        self.assertEqual(data["num_pages"], 1)

        # Check the number of requests
        self.assertEqual(len(data["domain_requests"]), 3)

        # Expected domain requests
        expected_domain_requests = [self.domain_requests[0], self.domain_requests[2], self.domain_requests[13]]

        # Extract fields from response
        domain_request_ids = [domain_request["id"] for domain_request in data["domain_requests"]]
        requested_domain = [domain_request["requested_domain"] for domain_request in data["domain_requests"]]
        creator = [domain_request["creator"] for domain_request in data["domain_requests"]]
        status = [domain_request["status"] for domain_request in data["domain_requests"]]
        action_urls = [domain_request["action_url"] for domain_request in data["domain_requests"]]
        action_labels = [domain_request["action_label"] for domain_request in data["domain_requests"]]
        svg_icons = [domain_request["svg_icon"] for domain_request in data["domain_requests"]]

        # Check fields for each domain_request
        for i, expected_domain_request in enumerate(expected_domain_requests):
            self.assertEqual(expected_domain_request.id, domain_request_ids[i])
            if expected_domain_request.requested_domain:
                self.assertEqual(expected_domain_request.requested_domain.name, requested_domain[i])
            else:
                self.assertIsNone(requested_domain[i])
            self.assertEqual(expected_domain_request.creator.email, creator[i])
            # Check action url, action label and svg icon
            # Example domain requests will test each of below three scenarios
            if creator[i] != self.user.email or not self.user.has_edit_request_portfolio_permission(self.portfolio):
                # Test case where action is View
                self.assertEqual("View", action_labels[i])
                self.assertEqual(
                    reverse("domain-request-status-viewonly", kwargs={"domain_request_pk": expected_domain_request.id}),
                    action_urls[i],
                )
                self.assertEqual("visibility", svg_icons[i])
            elif status[i] in [
                DomainRequest.DomainRequestStatus.STARTED.label,
                DomainRequest.DomainRequestStatus.ACTION_NEEDED.label,
                DomainRequest.DomainRequestStatus.WITHDRAWN.label,
            ]:
                # Test case where action is Edit
                self.assertEqual("Edit", action_labels[i])
                self.assertEqual(
                    reverse("edit-domain-request", kwargs={"id": expected_domain_request.id}), action_urls[i]
                )
                self.assertEqual("edit", svg_icons[i])
            else:
                # Test case where action is Manage
                self.assertEqual("Manage", action_labels[i])
                self.assertEqual(
                    reverse("domain-request-status", kwargs={"domain_request_pk": expected_domain_request.id}),
                    action_urls[i],
                )
                self.assertEqual("settings", svg_icons[i])

    def test_get_domain_requests_json_with_portfolio_edit_requests(self):
        """Test that an authenticated user gets the list of 2 requests for portfolio. The 2 requests
        are the requests that are associated with the portfolio and owned by self.user."""

        UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            additional_permissions=[UserPortfolioPermissionChoices.EDIT_REQUESTS],
        )

        response = self.app.get(reverse("get_domain_requests_json"), {"portfolio": self.portfolio.id})
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertFalse(data["has_next"])
        self.assertFalse(data["has_previous"])
        self.assertEqual(data["num_pages"], 1)

        # Check the number of requests
        self.assertEqual(len(data["domain_requests"]), 2)

        # Expected domain requests
        expected_domain_requests = [self.domain_requests[0], self.domain_requests[2]]

        # Extract fields from response, since other tests test all fields, only ids and requested
        # domains tested in this test
        domain_request_ids = [domain_request["id"] for domain_request in data["domain_requests"]]
        requested_domain = [domain_request["requested_domain"] for domain_request in data["domain_requests"]]

        # Check fields for each domain_request
        for i, expected_domain_request in enumerate(expected_domain_requests):
            self.assertEqual(expected_domain_request.id, domain_request_ids[i])
            if expected_domain_request.requested_domain:
                self.assertEqual(expected_domain_request.requested_domain.name, requested_domain[i])
            else:
                self.assertIsNone(requested_domain[i])

    def test_pagination(self):
        """Test that pagination works properly. There are 11 total non-approved requests and
        a page size of 10"""
        response = self.app.get(reverse("get_domain_requests_json"), {"page": 1})
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertTrue(data["has_next"])
        self.assertFalse(data["has_previous"])
        self.assertEqual(data["num_pages"], 2)

        response = self.app.get(reverse("get_domain_requests_json"), {"page": 2})
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 2)
        self.assertFalse(data["has_next"])
        self.assertTrue(data["has_previous"])
        self.assertEqual(data["num_pages"], 2)

    def test_sorting(self):
        """test that sorting works properly on the result set"""
        response = self.app.get(
            reverse("get_domain_requests_json"), {"sort_by": "last_submitted_date", "order": "desc"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check if sorted by last_submitted_date in descending order
        last_submitted_dates = [req["last_submitted_date"] for req in data["domain_requests"]]
        self.assertEqual(last_submitted_dates, sorted(last_submitted_dates, reverse=True))

        response = self.app.get(reverse("get_domain_requests_json"), {"sort_by": "last_submitted_date", "order": "asc"})
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check if sorted by last_submitted_date in ascending order
        last_submitted_dates = [req["last_submitted_date"] for req in data["domain_requests"]]
        self.assertEqual(last_submitted_dates, sorted(last_submitted_dates))

    def test_filter_approved_excluded(self):
        """test that approved requests are excluded from result set."""
        # sort in reverse chronological order of submission date, since most recent request is approved
        response = self.app.get(
            reverse("get_domain_requests_json"), {"sort_by": "last_submitted_date", "order": "desc"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Ensure no approved requests are included
        for domain_request in data["domain_requests"]:
            self.assertNotEqual(domain_request["status"], DomainRequest.DomainRequestStatus.APPROVED)

    def test_search(self):
        """Tests our search functionality. We expect that search filters on creator only when we are in a portfolio"""
        # Test search for domain name
        response = self.app.get(reverse("get_domain_requests_json"), {"search_term": "lamb"})
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(len(data["domain_requests"]), 1)

        requested_domain = data["domain_requests"][0]["requested_domain"]
        self.assertEqual(requested_domain, "lamb-chops.gov")

        # Test search for 'New domain request'
        response = self.app.get(reverse("get_domain_requests_json"), {"search_term": "new domain"})
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertTrue(any(req["requested_domain"] is None for req in data["domain_requests"]))

        # Test search with portfolio (including creator search)
        self.client.force_login(self.user)
        user_perm, _ = UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
        )
        response = self.app.get(
            reverse("get_domain_requests_json"), {"search_term": "info", "portfolio": self.portfolio.id}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertTrue(any(req["creator"].startswith("info") for req in data["domain_requests"]))

        # Test search without portfolio (should not search on creator)
        user_perm.delete()
        response = self.app.get(reverse("get_domain_requests_json"), {"search_term": "info"})
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(len(data["domain_requests"]), 0)

    def test_status_filter(self):
        """Test that status filtering works properly"""
        # Test a single status
        response = self.app.get(reverse("get_domain_requests_json"), {"status": "started"})
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertTrue(all(req["status"] == "Started" for req in data["domain_requests"]))

        # Test an invalid status
        response = self.app.get(reverse("get_domain_requests_json"), {"status": "approved"})
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(len(data["domain_requests"]), 0)

    def test_combined_filtering_and_sorting(self):
        """Test that combining filters and sorting works properly"""
        user_perm, _ = UserPortfolioPermission.objects.get_or_create(
            user=self.user,
            portfolio=self.portfolio,
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
        )
        self.client.force_login(self.user)
        response = self.app.get(
            reverse("get_domain_requests_json"),
            {"search_term": "beef", "status": "started", "portfolio": self.portfolio.id},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertTrue(all("beef" in req["requested_domain"] for req in data["domain_requests"]))
        self.assertTrue(all(req["status"] == "Started" for req in data["domain_requests"]))
        created_at_dates = [req["created_at"] for req in data["domain_requests"]]
        self.assertEqual(created_at_dates, sorted(created_at_dates, reverse=True))
        user_perm.delete()
