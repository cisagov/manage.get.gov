from registrar.models import DomainRequest
from django.urls import reverse
from .test_views import TestWithUser
from django_webtest import WebTest  # type: ignore


class DomainRequestViewTest(TestWithUser, WebTest):
    def setUp(self):
        super().setUp()
        self.app.set_user(self.user.username)

        # Create domain requests for the user
        self.domain_requests = [
            DomainRequest.objects.create(
                creator=self.user,
                requested_domain=None,  
                submission_date="2024-01-01",
                status=DomainRequest.DomainRequestStatus.STARTED,
                created_at="2024-01-01",
            ),
            DomainRequest.objects.create(
                creator=self.user,
                requested_domain=None,
                submission_date="2024-02-01",
                status=DomainRequest.DomainRequestStatus.WITHDRAWN,
                created_at="2024-02-01",
            ),
            DomainRequest.objects.create(
                creator=self.user,
                requested_domain=None,
                submission_date="2024-03-01",
                status=DomainRequest.DomainRequestStatus.REJECTED,
                created_at="2024-03-01",
            ),
            DomainRequest.objects.create(
                creator=self.user,
                requested_domain=None,
                submission_date="2024-04-01",
                status=DomainRequest.DomainRequestStatus.STARTED,
                created_at="2024-04-01",
            ),
            DomainRequest.objects.create(
                creator=self.user,
                requested_domain=None,  
                submission_date="2024-05-01",
                status=DomainRequest.DomainRequestStatus.STARTED,
                created_at="2024-05-01",
            ),
            DomainRequest.objects.create(
                creator=self.user,
                requested_domain=None,
                submission_date="2024-06-01",
                status=DomainRequest.DomainRequestStatus.WITHDRAWN,
                created_at="2024-06-01",
            ),
            DomainRequest.objects.create(
                creator=self.user,
                requested_domain=None,
                submission_date="2024-07-01",
                status=DomainRequest.DomainRequestStatus.REJECTED,
                created_at="2024-07-01",
            ),
            DomainRequest.objects.create(
                creator=self.user,
                requested_domain=None,
                submission_date="2024-08-01",
                status=DomainRequest.DomainRequestStatus.STARTED,
                created_at="2024-08-01",
            ),
            DomainRequest.objects.create(
                creator=self.user,
                requested_domain=None, 
                submission_date="2024-09-01",
                status=DomainRequest.DomainRequestStatus.STARTED,
                created_at="2024-09-01",
            ),
            DomainRequest.objects.create(
                creator=self.user,
                requested_domain=None,
                submission_date="2024-10-01",
                status=DomainRequest.DomainRequestStatus.WITHDRAWN,
                created_at="2024-10-01",
            ),
            DomainRequest.objects.create(
                creator=self.user,
                requested_domain=None,
                submission_date="2024-11-01",
                status=DomainRequest.DomainRequestStatus.REJECTED,
                created_at="2024-11-01",
            ),
            DomainRequest.objects.create(
                creator=self.user,
                requested_domain=None,
                submission_date="2024-12-01",
                status=DomainRequest.DomainRequestStatus.APPROVED,
                created_at="2024-12-01",
            ),
        ]

    def test_get_domain_requests_json_authenticated(self):
        """ test that domain requests are returned properly for an authenticated user """
        response = self.app.get(reverse("get_domain_requests_json"))
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check pagination info
        self.assertEqual(data["page"], 1)
        self.assertTrue(data["has_next"])
        self.assertFalse(data["has_previous"])
        self.assertEqual(data["num_pages"], 2)

        # Check domain requests
        self.assertEqual(len(data["domain_requests"]), 10)
        for domain_request in data["domain_requests"]:
            self.assertNotEqual(domain_request["status"], "Approved")

    def test_pagination(self):
        """ Test that pagination works properly. There are 11 total non-approved requests and
        a page size of 10 """
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
        """ test that sorting works properly on the result set """
        response = self.app.get(reverse("get_domain_requests_json"), {"sort_by": "submission_date", "order": "desc"})
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check if sorted by submission_date in descending order
        submission_dates = [req["submission_date"] for req in data["domain_requests"]]
        self.assertEqual(submission_dates, sorted(submission_dates, reverse=True))

        response = self.app.get(reverse("get_domain_requests_json"), {"sort_by": "submission_date", "order": "asc"})
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Check if sorted by submission_date in ascending order
        submission_dates = [req["submission_date"] for req in data["domain_requests"]]
        self.assertEqual(submission_dates, sorted(submission_dates))

    def test_filter_approved_excluded(self):
        """ test that approved requests are excluded from result set. """
        # sort in reverse chronological order of submission date, since most recent request is approved
        response = self.app.get(reverse("get_domain_requests_json"), {"sort_by": "submission_date", "order": "desc"})
        self.assertEqual(response.status_code, 200)
        data = response.json

        # Ensure no approved requests are included
        for domain_request in data["domain_requests"]:
            self.assertNotEqual(domain_request["status"], DomainRequest.DomainRequestStatus.APPROVED)
