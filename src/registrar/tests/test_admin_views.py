from django.test import TestCase, Client
from django.urls import reverse
from registrar.tests.common import create_superuser
from api.tests.common import less_console_noise_decorator


class TestAdminViews(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="localhost:8080")
        self.superuser = create_superuser()

    @less_console_noise_decorator
    def test_export_data_view(self):
        self.client.force_login(self.superuser)

        # Reverse the URL for the admin index page
        admin_index_url = reverse("admin:index")

        # Make a GET request to the admin index page
        response = self.client.get(admin_index_url)

        # Assert that the response status code is 200 (OK)
        self.assertEqual(response.status_code, 200)

        # Ensure that the start_date and end_date are set
        start_date = "2023-01-01"
        end_date = "2023-12-31"

        # Construct the URL for the export data view with start_date and end_date parameters:
        # This stuff is currently done in JS
        export_data_url = reverse("export_domains_growth") + f"?start_date={start_date}&end_date={end_date}"

        # Make a GET request to the export data page
        response = self.client.get(export_data_url)

        # Assert that the response status code is 200 (OK) or the expected status code
        self.assertEqual(response.status_code, 200)

        # Assert that the content type is CSV
        self.assertEqual(response["Content-Type"], "text/csv")

        # Check if the filename in the Content-Disposition header matches the expected pattern
        expected_filename = f"domain-growth-report-{start_date}-to-{end_date}.csv"
        self.assertIn(f'attachment; filename="{expected_filename}"', response["Content-Disposition"])
