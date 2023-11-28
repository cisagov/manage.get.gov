from unittest import skip
from django.test import Client, TestCase
from io import StringIO
import csv
from registrar.models.domain_information import DomainInformation
from registrar.models.domain import Domain
from registrar.models.user import User
from django.contrib.auth import get_user_model
from registrar.utility.csv_export import export_domains_to_writer
from django.core.management import call_command
from unittest.mock import call, mock_open, patch

class CsvReportsTest(TestCase):
    """Tests to determine if we are uploading our reports correctly"""
    def setUp(self):
        """Create fake domain data"""
        self.client = Client(HTTP_HOST="localhost:8080")

        username = "test_user"
        first_name = "First"
        last_name = "Last"
        email = "info@example.com"
        self.user = get_user_model().objects.create(
            username=username, first_name=first_name, last_name=last_name, email=email
        )

        self.domain_1, _ = Domain.objects.get_or_create(name="cdomain1.gov", state=Domain.State.READY)
        self.domain_2, _ = Domain.objects.get_or_create(name="adomain2.gov", state=Domain.State.DNS_NEEDED)
        self.domain_3, _ = Domain.objects.get_or_create(name="ddomain3.gov", state=Domain.State.ON_HOLD)
        self.domain_4, _ = Domain.objects.get_or_create(name="bdomain4.gov", state=Domain.State.UNKNOWN)
        self.domain_4, _ = Domain.objects.get_or_create(name="bdomain4.gov", state=Domain.State.UNKNOWN)

        self.domain_information_1, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_1,
            organization_type="federal",
            federal_agency="World War I Centennial Commission",
            federal_type="executive",
        )
        self.domain_information_2, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_2,
            organization_type="interstate",
        )
        self.domain_information_3, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_3,
            organization_type="federal",
            federal_agency="Armed Forces Retirement Home",
        )
        self.domain_information_4, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_4,
            organization_type="federal",
            federal_agency="Armed Forces Retirement Home",
        )

    def tearDown(self):
        """Delete all faked data"""
        Domain.objects.all().delete()
        DomainInformation.objects.all().delete()
        User.objects.all().delete()
        super().tearDown()

    def test_create_failed_federal(self):
        """Ensures that we return an error when we cannot find our created file"""
        fake_open = mock_open()
        # We don't actually want to write anything for a test case,
        # we just want to verify what is being written.
        with patch('builtins.open', fake_open), self.assertRaises(FileNotFoundError) as err:
            call_command(
                "generate_current_federal_report"
            )
        error = err.exception
        self.assertEqual(str(error), "Could not find newly created file at 'migrationdata/current-federal.csv'")

    def test_create_failed_full(self):
        """Ensures that we return an error when we cannot find our created file"""
        fake_open = mock_open()
        # We don't actually want to write anything for a test case,
        # we just want to verify what is being written.
        with patch('builtins.open', fake_open), self.assertRaises(FileNotFoundError) as err:
            call_command(
                "generate_current_full_report"
            )
        error = err.exception
        self.assertEqual(str(error), "Could not find newly created file at 'migrationdata/current-full.csv'")

    def test_generate_federal_report(self):
        """Ensures that we correctly generate current-federal.csv"""
        expected_file_content = [
            call('Domain name,Domain type,Agency,Organization name,City,State,Security Contact Email\r\n'),
            call('cdomain1.gov,Federal - Executive,World War I Centennial Commission,,,, \r\n'),
            call('ddomain3.gov,Federal,Armed Forces Retirement Home,,,, \r\n')
        ]
        fake_open = mock_open()
        # We don't actually want to write anything for a test case,
        # we just want to verify what is being written.
        with patch('builtins.open', fake_open):
            call_command(
                "generate_current_federal_report",
                checkpath=False
            )
        content = fake_open()
        # Now you can make assertions about how you expect 'file' to be used.
        content.write.assert_has_calls(expected_file_content)

    def test_generate_full_report(self):
        """Ensures that we correctly generate current-full.csv"""
        expected_file_content = [
            call('Domain name,Domain type,Agency,Organization name,City,State,Security Contact Email\r\n'),
            call('cdomain1.gov,Federal - Executive,World War I Centennial Commission,,,, \r\n'),
            call('ddomain3.gov,Federal,Armed Forces Retirement Home,,,, \r\n'),
            call('adomain2.gov,Interstate,,,,, \r\n')
        ]
        fake_open = mock_open()
        # We don't actually want to write anything for a test case,
        # we just want to verify what is being written.
        with patch('builtins.open', fake_open):
            call_command(
                "generate_current_full_report",
                checkpath=False
            )
        content = fake_open()
        # Now you can make assertions about how you expect 'file' to be used.
        content.write.assert_has_calls(expected_file_content)
    
    def test_not_found_full_report(self):
        """Ensures that we get a not found when the report doesn't exist"""
        response = self.client.get('/api/v1/get-report/current-full')

        # Check that the response has status code 404
        self.assertEqual(response.status_code, 404)
        # Check that the response body contains "File not found"
        self.assertEqual(response.content.decode(), "File not found")

    def test_not_found_federal_report(self):
        """Ensures that we get a not found when the report doesn't exist"""
        response = self.client.get('/api/v1/get-report/current-federal')

        # Check that the response has status code 404
        self.assertEqual(response.status_code, 404)
        # Check that the response body contains "File not found"
        self.assertEqual(response.content.decode(), "File not found")
    
    def test_federal_report(self):
        """Ensures that we get a not found when the report doesn't exist"""
        response = self.client.get('/api/v1/get-report/current-federal')

        # Check that the response has status code 404
        self.assertEqual(response.status_code, 404)
        # Check that the response body contains "File not found"
        self.assertEqual(response.content.decode(), "File not found")


class ExportDataTest(TestCase):
    def setUp(self):
        username = "test_user"
        first_name = "First"
        last_name = "Last"
        email = "info@example.com"
        self.user = get_user_model().objects.create(
            username=username, first_name=first_name, last_name=last_name, email=email
        )

        self.domain_1, _ = Domain.objects.get_or_create(name="cdomain1.gov", state=Domain.State.READY)
        self.domain_2, _ = Domain.objects.get_or_create(name="adomain2.gov", state=Domain.State.DNS_NEEDED)
        self.domain_3, _ = Domain.objects.get_or_create(name="ddomain3.gov", state=Domain.State.ON_HOLD)
        self.domain_4, _ = Domain.objects.get_or_create(name="bdomain4.gov", state=Domain.State.UNKNOWN)
        self.domain_4, _ = Domain.objects.get_or_create(name="bdomain4.gov", state=Domain.State.UNKNOWN)

        self.domain_information_1, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_1,
            organization_type="federal",
            federal_agency="World War I Centennial Commission",
            federal_type="executive",
        )
        self.domain_information_2, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_2,
            organization_type="interstate",
        )
        self.domain_information_3, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_3,
            organization_type="federal",
            federal_agency="Armed Forces Retirement Home",
        )
        self.domain_information_4, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_4,
            organization_type="federal",
            federal_agency="Armed Forces Retirement Home",
        )

    def tearDown(self):
        Domain.objects.all().delete()
        DomainInformation.objects.all().delete()
        User.objects.all().delete()
        super().tearDown()

    def test_export_domains_to_writer(self):
        """Test that export_domains_to_writer returns the
        existing domain, test that sort by domain name works,
        test that filter works"""
        # Create a CSV file in memory
        csv_file = StringIO()
        writer = csv.writer(csv_file)

        # Define columns, sort fields, and filter condition
        columns = [
            "Domain name",
            "Domain type",
            "Agency",
            "Organization name",
            "City",
            "State",
            "AO",
            "AO email",
            "Submitter",
            "Submitter title",
            "Submitter email",
            "Submitter phone",
            "Security Contact Email",
            "Status",
        ]
        sort_fields = ["domain__name"]
        filter_condition = {
            "domain__state__in": [
                Domain.State.READY,
                Domain.State.DNS_NEEDED,
                Domain.State.ON_HOLD,
            ],
        }

        # Call the export function
        export_domains_to_writer(writer, columns, sort_fields, filter_condition)

        # Reset the CSV file's position to the beginning
        csv_file.seek(0)

        # Read the content into a variable
        csv_content = csv_file.read()

        # We expect READY domains,
        # sorted alphabetially by domain name
        expected_content = (
            "Domain name,Domain type,Agency,Organization name,City,State,AO,"
            "AO email,Submitter,Submitter title,Submitter email,Submitter phone,"
            "Security Contact Email,Status\n"
            "adomain2.gov,Interstate,dnsneeded\n"
            "cdomain1.gov,Federal - Executive,World War I Centennial Commission,ready\n"
            "ddomain3.gov,Federal,Armed Forces Retirement Home,onhold\n"
        )

        # Normalize line endings and remove commas,
        # spaces and leading/trailing whitespace
        csv_content = csv_content.replace(",,", "").replace(",", "").replace(" ", "").replace("\r\n", "\n").strip()
        expected_content = expected_content.replace(",,", "").replace(",", "").replace(" ", "").strip()

        self.assertEqual(csv_content, expected_content)

    def test_export_domains_to_writer_additional(self):
        """An additional test for filters and multi-column sort"""
        # Create a CSV file in memory
        csv_file = StringIO()
        writer = csv.writer(csv_file)

        # Define columns, sort fields, and filter condition
        columns = [
            "Domain name",
            "Domain type",
            "Agency",
            "Organization name",
            "City",
            "State",
            "Security Contact Email",
        ]
        sort_fields = ["domain__name", "federal_agency", "organization_type"]
        filter_condition = {
            "organization_type__icontains": "federal",
            "domain__state__in": [
                Domain.State.READY,
                Domain.State.DNS_NEEDED,
                Domain.State.ON_HOLD,
            ],
        }

        # Call the export function
        export_domains_to_writer(writer, columns, sort_fields, filter_condition)

        # Reset the CSV file's position to the beginning
        csv_file.seek(0)

        # Read the content into a variable
        csv_content = csv_file.read()

        # We expect READY domains,
        # federal only
        # sorted alphabetially by domain name
        expected_content = (
            "Domain name,Domain type,Agency,Organization name,City,"
            "State,Security Contact Email\n"
            "cdomain1.gov,Federal - Executive,World War I Centennial Commission\n"
            "ddomain3.gov,Federal,Armed Forces Retirement Home\n"
        )

        # Normalize line endings and remove commas,
        # spaces and leading/trailing whitespace
        csv_content = csv_content.replace(",,", "").replace(",", "").replace(" ", "").replace("\r\n", "\n").strip()
        expected_content = expected_content.replace(",,", "").replace(",", "").replace(" ", "").strip()

        self.assertEqual(csv_content, expected_content)
