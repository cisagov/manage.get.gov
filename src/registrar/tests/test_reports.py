import csv
import io
from django.test import Client, RequestFactory
from io import StringIO
from registrar.models.domain_request import DomainRequest
from registrar.models.domain import Domain
from registrar.utility.csv_export import (
    export_data_managed_domains_to_csv,
    export_data_unmanaged_domains_to_csv,
    get_sliced_domains,
    get_sliced_requests,
    write_csv_for_domains,
    get_default_start_date,
    get_default_end_date,
    write_csv_for_requests,
)

from django.core.management import call_command
from unittest.mock import MagicMock, call, mock_open, patch
from api.views import get_current_federal, get_current_full
from django.conf import settings
from botocore.exceptions import ClientError
import boto3_mocking
from registrar.utility.s3_bucket import S3ClientError, S3ClientErrorCodes  # type: ignore
from django.utils import timezone
from .common import MockDb, MockEppLib, less_console_noise


class CsvReportsTest(MockDb):
    """Tests to determine if we are uploading our reports correctly"""

    def setUp(self):
        """Create fake domain data"""
        super().setUp()
        self.client = Client(HTTP_HOST="localhost:8080")
        self.factory = RequestFactory()

    @boto3_mocking.patching
    def test_generate_federal_report(self):
        """Ensures that we correctly generate current-federal.csv"""
        with less_console_noise():
            mock_client = MagicMock()
            fake_open = mock_open()
            expected_file_content = [
                call("Domain name,Domain type,Agency,Organization name,City,State,Security contact email\r\n"),
                call("cdomain11.gov,Federal - Executive,World War I Centennial Commission,,,, \r\n"),
                call("cdomain1.gov,Federal - Executive,World War I Centennial Commission,,,, \r\n"),
                call("adomain10.gov,Federal,Armed Forces Retirement Home,,,, \r\n"),
                call("ddomain3.gov,Federal,Armed Forces Retirement Home,,,, \r\n"),
            ]
            # We don't actually want to write anything for a test case,
            # we just want to verify what is being written.
            with boto3_mocking.clients.handler_for("s3", mock_client):
                with patch("builtins.open", fake_open):
                    call_command("generate_current_federal_report", checkpath=False)
            content = fake_open()

            content.write.assert_has_calls(expected_file_content)

    @boto3_mocking.patching
    def test_generate_full_report(self):
        """Ensures that we correctly generate current-full.csv"""
        with less_console_noise():
            mock_client = MagicMock()
            fake_open = mock_open()
            expected_file_content = [
                call("Domain name,Domain type,Agency,Organization name,City,State,Security contact email\r\n"),
                call("cdomain11.gov,Federal - Executive,World War I Centennial Commission,,,, \r\n"),
                call("cdomain1.gov,Federal - Executive,World War I Centennial Commission,,,, \r\n"),
                call("adomain10.gov,Federal,Armed Forces Retirement Home,,,, \r\n"),
                call("ddomain3.gov,Federal,Armed Forces Retirement Home,,,, \r\n"),
                call("adomain2.gov,Interstate,,,,, \r\n"),
            ]
            # We don't actually want to write anything for a test case,
            # we just want to verify what is being written.
            with boto3_mocking.clients.handler_for("s3", mock_client):
                with patch("builtins.open", fake_open):
                    call_command("generate_current_full_report", checkpath=False)
            content = fake_open()

            content.write.assert_has_calls(expected_file_content)

    @boto3_mocking.patching
    def test_not_found_full_report(self):
        """Ensures that we get a not found when the report doesn't exist"""

        def side_effect(Bucket, Key):
            raise ClientError({"Error": {"Code": "NoSuchKey", "Message": "No such key"}}, "get_object")

        with less_console_noise():
            mock_client = MagicMock()
            mock_client.get_object.side_effect = side_effect

            response = None
            with boto3_mocking.clients.handler_for("s3", mock_client):
                with patch("boto3.client", return_value=mock_client):
                    with self.assertRaises(S3ClientError) as context:
                        response = self.client.get("/api/v1/get-report/current-full")
                        # Check that the response has status code 500
                        self.assertEqual(response.status_code, 500)

            # Check that we get the right error back from the page
            self.assertEqual(context.exception.code, S3ClientErrorCodes.FILE_NOT_FOUND_ERROR)

    @boto3_mocking.patching
    def test_not_found_federal_report(self):
        """Ensures that we get a not found when the report doesn't exist"""

        def side_effect(Bucket, Key):
            raise ClientError({"Error": {"Code": "NoSuchKey", "Message": "No such key"}}, "get_object")

        with less_console_noise():
            mock_client = MagicMock()
            mock_client.get_object.side_effect = side_effect

            with boto3_mocking.clients.handler_for("s3", mock_client):
                with patch("boto3.client", return_value=mock_client):
                    with self.assertRaises(S3ClientError) as context:
                        response = self.client.get("/api/v1/get-report/current-federal")
                        # Check that the response has status code 500
                        self.assertEqual(response.status_code, 500)

            # Check that we get the right error back from the page
            self.assertEqual(context.exception.code, S3ClientErrorCodes.FILE_NOT_FOUND_ERROR)

    @boto3_mocking.patching
    def test_load_federal_report(self):
        """Tests the get_current_federal api endpoint"""

        with less_console_noise():
            mock_client = MagicMock()
            mock_client_instance = mock_client.return_value

            with open("registrar/tests/data/fake_current_federal.csv", "r") as file:
                file_content = file.read()

            # Mock a recieved file
            mock_client_instance.get_object.return_value = {"Body": io.BytesIO(file_content.encode())}
            with boto3_mocking.clients.handler_for("s3", mock_client):
                request = self.factory.get("/fake-path")
                response = get_current_federal(request)

            # Check that we are sending the correct calls.
            # Ensures that we are decoding the file content recieved from AWS.
            expected_call = [call.get_object(Bucket=settings.AWS_S3_BUCKET_NAME, Key="current-federal.csv")]
            mock_client_instance.assert_has_calls(expected_call)

            # Check that the response has status code 200
            self.assertEqual(response.status_code, 200)

            # Check that the response contains what we expect
            expected_file_content = (
                "Domain name,Domain type,Agency,Organization name,City,State,Security contact email\n"
                "cdomain1.gov,Federal - Executive,World War I Centennial Commission,,,,\n"
                "ddomain3.gov,Federal,Armed Forces Retirement Home,,,,"
            ).encode()

            self.assertEqual(expected_file_content, response.content)

    @boto3_mocking.patching
    def test_load_full_report(self):
        """Tests the current-federal api link"""

        with less_console_noise():
            mock_client = MagicMock()
            mock_client_instance = mock_client.return_value

            with open("registrar/tests/data/fake_current_full.csv", "r") as file:
                file_content = file.read()

            # Mock a recieved file
            mock_client_instance.get_object.return_value = {"Body": io.BytesIO(file_content.encode())}
            with boto3_mocking.clients.handler_for("s3", mock_client):
                request = self.factory.get("/fake-path")
                response = get_current_full(request)

            # Check that we are sending the correct calls.
            # Ensures that we are decoding the file content recieved from AWS.
            expected_call = [call.get_object(Bucket=settings.AWS_S3_BUCKET_NAME, Key="current-full.csv")]
            mock_client_instance.assert_has_calls(expected_call)

            # Check that the response has status code 200
            self.assertEqual(response.status_code, 200)

            # Check that the response contains what we expect
            expected_file_content = (
                "Domain name,Domain type,Agency,Organization name,City,State,Security contact email\n"
                "cdomain1.gov,Federal - Executive,World War I Centennial Commission,,,,\n"
                "ddomain3.gov,Federal,Armed Forces Retirement Home,,,,\n"
                "adomain2.gov,Interstate,,,,,"
            ).encode()

            self.assertEqual(expected_file_content, response.content)


class ExportDataTest(MockDb, MockEppLib):
    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_export_domains_to_writer_security_emails_and_first_ready(self):
        """Test that export_domains_to_writer returns the
        expected security email and first_ready value"""

        with less_console_noise():
            # Add security email information
            self.domain_1.name = "defaultsecurity.gov"
            self.domain_1.save()
            # Invoke setter
            self.domain_1.security_contact
            # Invoke setter
            self.domain_2.security_contact
            # Invoke setter
            self.domain_3.security_contact

            # Add a first ready date on the first domain. Leaving the others blank.
            self.domain_1.first_ready = get_default_start_date()
            self.domain_1.save()

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
                "Security contact email",
                "Status",
                "Expiration date",
                "First ready on",
            ]
            sort_fields = ["domain__name"]
            filter_condition = {
                "domain__state__in": [
                    Domain.State.READY,
                    Domain.State.DNS_NEEDED,
                    Domain.State.ON_HOLD,
                ],
            }
            self.maxDiff = None
            # Call the export functions
            write_csv_for_domains(
                writer,
                columns,
                sort_fields,
                filter_condition,
                should_get_domain_managers=False,
                should_write_header=True,
            )

            # Reset the CSV file's position to the beginning
            csv_file.seek(0)
            # Read the content into a variable
            csv_content = csv_file.read()
            # We expect READY domains,
            # sorted alphabetially by domain name
            expected_content = (
                "Domain name,Domain type,Agency,Organization name,City,State,AO,"
                "AO email,Security contact email,Status,Expiration date, First ready on\n"
                "adomain10.gov,Federal,Armed Forces Retirement Home,Ready,2024-05-09\n"
                "adomain2.gov,Interstate,(blank),Dns needed,(blank)\n"
                "cdomain11.govFederal-ExecutiveWorldWarICentennialCommissionReady,2024-05-08\n"
                "ddomain3.gov,Federal,Armed Forces Retirement Home,security@mail.gov,On hold,2023-11-15,(blank)\n"
                "defaultsecurity.gov,Federal - Executive,World War I Centennial Commission,(blank),Ready,2023-11-01\n"
                "zdomain12.govInterstateReady,2024-05-08\n"
            )
            # Normalize line endings and remove commas,
            # spaces and leading/trailing whitespace
            csv_content = csv_content.replace(",,", "").replace(",", "").replace(" ", "").replace("\r\n", "\n").strip()
            expected_content = expected_content.replace(",,", "").replace(",", "").replace(" ", "").strip()
            self.assertEqual(csv_content, expected_content)

    def test_write_csv_for_domains(self):
        """Test that write_body returns the
        existing domain, test that sort by domain name works,
        test that filter works"""

        with less_console_noise():
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
                "Security contact email",
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
            # Call the export functions
            write_csv_for_domains(
                writer,
                columns,
                sort_fields,
                filter_condition,
                should_get_domain_managers=False,
                should_write_header=True,
            )
            # Reset the CSV file's position to the beginning
            csv_file.seek(0)
            # Read the content into a variable
            csv_content = csv_file.read()
            # We expect READY domains,
            # sorted alphabetially by domain name
            expected_content = (
                "Domain name,Domain type,Agency,Organization name,City,State,AO,"
                "AO email,Submitter,Submitter title,Submitter email,Submitter phone,"
                "Security contact email,Status\n"
                "adomain10.gov,Federal,Armed Forces Retirement Home,Ready\n"
                "adomain2.gov,Interstate,Dns needed\n"
                "cdomain11.govFederal-ExecutiveWorldWarICentennialCommissionReady\n"
                "cdomain1.gov,Federal - Executive,World War I Centennial Commission,Ready\n"
                "ddomain3.gov,Federal,Armed Forces Retirement Home,On hold\n"
                "zdomain12.govInterstateReady\n"
            )
            # Normalize line endings and remove commas,
            # spaces and leading/trailing whitespace
            csv_content = csv_content.replace(",,", "").replace(",", "").replace(" ", "").replace("\r\n", "\n").strip()
            expected_content = expected_content.replace(",,", "").replace(",", "").replace(" ", "").strip()
            self.assertEqual(csv_content, expected_content)

    def test_write_domains_body_additional(self):
        """An additional test for filters and multi-column sort"""

        with less_console_noise():
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
                "Security contact email",
            ]
            sort_fields = ["domain__name", "federal_agency", "generic_org_type"]
            filter_condition = {
                "generic_org_type__icontains": "federal",
                "domain__state__in": [
                    Domain.State.READY,
                    Domain.State.DNS_NEEDED,
                    Domain.State.ON_HOLD,
                ],
            }
            # Call the export functions
            write_csv_for_domains(
                writer,
                columns,
                sort_fields,
                filter_condition,
                should_get_domain_managers=False,
                should_write_header=True,
            )
            # Reset the CSV file's position to the beginning
            csv_file.seek(0)
            # Read the content into a variable
            csv_content = csv_file.read()
            # We expect READY domains,
            # federal only
            # sorted alphabetially by domain name
            expected_content = (
                "Domain name,Domain type,Agency,Organization name,City,"
                "State,Security contact email\n"
                "adomain10.gov,Federal,Armed Forces Retirement Home\n"
                "cdomain11.govFederal-ExecutiveWorldWarICentennialCommission\n"
                "cdomain1.gov,Federal - Executive,World War I Centennial Commission\n"
                "ddomain3.gov,Federal,Armed Forces Retirement Home\n"
            )
            # Normalize line endings and remove commas,
            # spaces and leading/trailing whitespace
            csv_content = csv_content.replace(",,", "").replace(",", "").replace(" ", "").replace("\r\n", "\n").strip()
            expected_content = expected_content.replace(",,", "").replace(",", "").replace(" ", "").strip()
            self.assertEqual(csv_content, expected_content)

    def test_write_domains_body_with_date_filter_pulls_domains_in_range(self):
        """Test that domains that are
            1. READY and their first_ready dates are in range
            2. DELETED and their deleted dates are in range
        are pulled when the growth report conditions are applied to export_domains_to_writed.
        Test that ready domains are sorted by first_ready/deleted dates first, names second.

        We considered testing export_data_domain_growth_to_csv which calls write_body
        and would have been easy to set up, but expected_content would contain created_at dates
        which are hard to mock.

        TODO: Simplify if created_at is not needed for the report."""

        with less_console_noise():
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
                "Status",
                "Expiration date",
            ]
            sort_fields = [
                "created_at",
                "domain__name",
            ]
            sort_fields_for_deleted_domains = [
                "domain__deleted",
                "domain__name",
            ]
            filter_condition = {
                "domain__state__in": [
                    Domain.State.READY,
                ],
                "domain__first_ready__lte": self.end_date,
                "domain__first_ready__gte": self.start_date,
            }
            filter_conditions_for_deleted_domains = {
                "domain__state__in": [
                    Domain.State.DELETED,
                ],
                "domain__deleted__lte": self.end_date,
                "domain__deleted__gte": self.start_date,
            }

            # Call the export functions
            write_csv_for_domains(
                writer,
                columns,
                sort_fields,
                filter_condition,
                should_get_domain_managers=False,
                should_write_header=True,
            )
            write_csv_for_domains(
                writer,
                columns,
                sort_fields_for_deleted_domains,
                filter_conditions_for_deleted_domains,
                should_get_domain_managers=False,
                should_write_header=False,
            )
            # Reset the CSV file's position to the beginning
            csv_file.seek(0)

            # Read the content into a variable
            csv_content = csv_file.read()

            # We expect READY domains first, created between today-2 and today+2, sorted by created_at then name
            # and DELETED domains deleted between today-2 and today+2, sorted by deleted then name
            expected_content = (
                "Domain name,Domain type,Agency,Organization name,City,"
                "State,Status,Expiration date\n"
                "cdomain1.gov,Federal-Executive,World War I Centennial Commission,,,,Ready,\n"
                "adomain10.gov,Federal,Armed Forces Retirement Home,,,,Ready,\n"
                "cdomain11.govFederal-ExecutiveWorldWarICentennialCommissionReady\n"
                "zdomain12.govInterstateReady\n"
                "zdomain9.gov,Federal,Armed Forces Retirement Home,,,,Deleted,\n"
                "sdomain8.gov,Federal,Armed Forces Retirement Home,,,,Deleted,\n"
                "xdomain7.gov,Federal,Armed Forces Retirement Home,,,,Deleted,\n"
            )

            # Normalize line endings and remove commas,
            # spaces and leading/trailing whitespace
            csv_content = csv_content.replace(",,", "").replace(",", "").replace(" ", "").replace("\r\n", "\n").strip()
            expected_content = expected_content.replace(",,", "").replace(",", "").replace(" ", "").strip()

            self.assertEqual(csv_content, expected_content)

    def test_export_domains_to_writer_domain_managers(self):
        """Test that export_domains_to_writer returns the
        expected domain managers.

        An invited user, woofwardthethird, should also be pulled into this report.

        squeaker@rocks.com is invited to domain2 (DNS_NEEDED) and domain10 (No managers).
        She should show twice in this report but not in test_export_data_managed_domains_to_csv."""

        with less_console_noise():
            # Create a CSV file in memory
            csv_file = StringIO()
            writer = csv.writer(csv_file)
            # Define columns, sort fields, and filter condition
            columns = [
                "Domain name",
                "Status",
                "Expiration date",
                "Domain type",
                "Agency",
                "Organization name",
                "City",
                "State",
                "AO",
                "AO email",
                "Security contact email",
            ]
            sort_fields = ["domain__name"]
            filter_condition = {
                "domain__state__in": [
                    Domain.State.READY,
                    Domain.State.DNS_NEEDED,
                    Domain.State.ON_HOLD,
                ],
            }
            self.maxDiff = None
            # Call the export functions
            write_csv_for_domains(
                writer,
                columns,
                sort_fields,
                filter_condition,
                should_get_domain_managers=True,
                should_write_header=True,
            )

            # Reset the CSV file's position to the beginning
            csv_file.seek(0)
            # Read the content into a variable
            csv_content = csv_file.read()
            # We expect READY domains,
            # sorted alphabetially by domain name
            expected_content = (
                "Domain name,Status,Expiration date,Domain type,Agency,"
                "Organization name,City,State,AO,AO email,"
                "Security contact email,Domain manager 1,DM1 status,Domain manager 2,DM2 status,"
                "Domain manager 3,DM3 status,Domain manager 4,DM4 status\n"
                "adomain10.gov,Ready,,Federal,Armed Forces Retirement Home,,,, , ,squeaker@rocks.com, I\n"
                "adomain2.gov,Dns needed,,Interstate,,,,, , , ,meoward@rocks.com, R,squeaker@rocks.com, I\n"
                "cdomain11.govReadyFederal-ExecutiveWorldWarICentennialCommissionmeoward@rocks.comR\n"
                "cdomain1.gov,Ready,,Federal - Executive,World War I Centennial Commission,,,"
                ", , , ,meoward@rocks.com,R,info@example.com,R,big_lebowski@dude.co,R,"
                "woofwardthethird@rocks.com,I\n"
                "ddomain3.gov,On hold,,Federal,Armed Forces Retirement Home,,,, , , ,,\n"
                "zdomain12.govReadyInterstatemeoward@rocks.comR\n"
            )
            # Normalize line endings and remove commas,
            # spaces and leading/trailing whitespace
            csv_content = csv_content.replace(",,", "").replace(",", "").replace(" ", "").replace("\r\n", "\n").strip()
            expected_content = expected_content.replace(",,", "").replace(",", "").replace(" ", "").strip()
            self.assertEqual(csv_content, expected_content)

    def test_export_data_managed_domains_to_csv(self):
        """Test get counts for domains that have domain managers for two different dates,
        get list of managed domains at end_date.

        An invited user, woofwardthethird, should also be pulled into this report."""

        with less_console_noise():
            # Create a CSV file in memory
            csv_file = StringIO()
            export_data_managed_domains_to_csv(
                csv_file, self.start_date.strftime("%Y-%m-%d"), self.end_date.strftime("%Y-%m-%d")
            )

            # Reset the CSV file's position to the beginning
            csv_file.seek(0)
            # Read the content into a variable
            csv_content = csv_file.read()
            self.maxDiff = None
            # We expect the READY domain names with the domain managers: Their counts, and listing at end_date.
            expected_content = (
                "MANAGED DOMAINS COUNTS AT START DATE\n"
                "Total,Federal,Interstate,State or territory,Tribal,County,City,Special district,"
                "School district,Election office\n"
                "0,0,0,0,0,0,0,0,0,0\n"
                "\n"
                "MANAGED DOMAINS COUNTS AT END DATE\n"
                "Total,Federal,Interstate,State or territory,Tribal,County,City,"
                "Special district,School district,Election office\n"
                "3,2,1,0,0,0,0,0,0,0\n"
                "\n"
                "Domain name,Domain type,Domain manager 1,DM1 status,Domain manager 2,DM2 status,"
                "Domain manager 3,DM3 status,Domain manager 4,DM4 status\n"
                "cdomain11.govFederal-Executivemeoward@rocks.com, R\n"
                "cdomain1.gov,Federal - Executive,meoward@rocks.com,R,info@example.com,R,"
                "big_lebowski@dude.co,R,woofwardthethird@rocks.com,I\n"
                "zdomain12.govInterstatemeoward@rocks.com,R\n"
            )

            # Normalize line endings and remove commas,
            # spaces and leading/trailing whitespace
            csv_content = csv_content.replace(",,", "").replace(",", "").replace(" ", "").replace("\r\n", "\n").strip()
            expected_content = expected_content.replace(",,", "").replace(",", "").replace(" ", "").strip()

            self.assertEqual(csv_content, expected_content)

    def test_export_data_unmanaged_domains_to_csv(self):
        """Test get counts for domains that do not have domain managers for two different dates,
        get list of unmanaged domains at end_date."""

        with less_console_noise():
            # Create a CSV file in memory
            csv_file = StringIO()
            export_data_unmanaged_domains_to_csv(
                csv_file, self.start_date.strftime("%Y-%m-%d"), self.end_date.strftime("%Y-%m-%d")
            )

            # Reset the CSV file's position to the beginning
            csv_file.seek(0)
            # Read the content into a variable
            csv_content = csv_file.read()
            self.maxDiff = None
            # We expect the READY domain names with the domain managers: Their counts, and listing at end_date.
            expected_content = (
                "UNMANAGED DOMAINS AT START DATE\n"
                "Total,Federal,Interstate,State or territory,Tribal,County,City,Special district,"
                "School district,Election office\n"
                "0,0,0,0,0,0,0,0,0,0\n"
                "\n"
                "UNMANAGED DOMAINS AT END DATE\n"
                "Total,Federal,Interstate,State or territory,Tribal,County,City,Special district,"
                "School district,Election office\n"
                "1,1,0,0,0,0,0,0,0,0\n"
                "\n"
                "Domain name,Domain type\n"
                "adomain10.gov,Federal\n"
            )

            # Normalize line endings and remove commas,
            # spaces and leading/trailing whitespace
            csv_content = csv_content.replace(",,", "").replace(",", "").replace(" ", "").replace("\r\n", "\n").strip()
            expected_content = expected_content.replace(",,", "").replace(",", "").replace(" ", "").strip()

            self.assertEqual(csv_content, expected_content)

    def test_write_requests_body_with_date_filter_pulls_requests_in_range(self):
        """Test that requests that are
            1. SUBMITTED and their submission_date are in range
        are pulled when the growth report conditions are applied to export_requests_to_writed.
        Test that requests  are sorted by requested domain name.
        """

        with less_console_noise():
            # Create a CSV file in memory
            csv_file = StringIO()
            writer = csv.writer(csv_file)
            # Define columns, sort fields, and filter condition
            # We'll skip submission date because it's dynamic and therefore
            # impossible to set in expected_content
            columns = [
                "Requested domain",
                "Organization type",
            ]
            sort_fields = [
                "requested_domain__name",
            ]
            filter_condition = {
                "status": DomainRequest.DomainRequestStatus.SUBMITTED,
                "submission_date__lte": self.end_date,
                "submission_date__gte": self.start_date,
            }
            write_csv_for_requests(writer, columns, sort_fields, filter_condition, should_write_header=True)
            # Reset the CSV file's position to the beginning
            csv_file.seek(0)
            # Read the content into a variable
            csv_content = csv_file.read()
            # We expect READY domains first, created between today-2 and today+2, sorted by created_at then name
            # and DELETED domains deleted between today-2 and today+2, sorted by deleted then name
            expected_content = (
                "Requested domain,Organization type\n"
                "city3.gov,Federal - Executive\n"
                "city4.gov,Federal - Executive\n"
            )

            # Normalize line endings and remove commas,
            # spaces and leading/trailing whitespace
            csv_content = csv_content.replace(",,", "").replace(",", "").replace(" ", "").replace("\r\n", "\n").strip()
            expected_content = expected_content.replace(",,", "").replace(",", "").replace(" ", "").strip()

            self.assertEqual(csv_content, expected_content)


class HelperFunctions(MockDb):
    """This asserts that 1=1. Its limited usefulness lies in making sure the helper methods stay healthy."""

    def test_get_default_start_date(self):
        expected_date = self.get_time_aware_date()
        actual_date = get_default_start_date()
        self.assertEqual(actual_date, expected_date)

    def test_get_default_end_date(self):
        # Note: You may need to mock timezone.now() for accurate testing
        expected_date = timezone.now()
        actual_date = get_default_end_date()
        self.assertEqual(actual_date.date(), expected_date.date())

    def test_get_sliced_domains(self):
        """Should get fitered domains counts sliced by org type and election office."""

        with less_console_noise():
            filter_condition = {
                "domain__permissions__isnull": False,
                "domain__first_ready__lte": self.end_date,
            }
            # Test with distinct
            managed_domains_sliced_at_end_date = get_sliced_domains(filter_condition)
            expected_content = [3, 2, 1, 0, 0, 0, 0, 0, 0, 0]
            self.assertEqual(managed_domains_sliced_at_end_date, expected_content)

            # Test without distinct
            managed_domains_sliced_at_end_date = get_sliced_domains(filter_condition)
            expected_content = [3, 2, 1, 0, 0, 0, 0, 0, 0, 0]
            self.assertEqual(managed_domains_sliced_at_end_date, expected_content)

    def test_get_sliced_requests(self):
        """Should get fitered requests counts sliced by org type and election office."""

        with less_console_noise():
            filter_condition = {
                "status": DomainRequest.DomainRequestStatus.SUBMITTED,
                "submission_date__lte": self.end_date,
            }
            submitted_requests_sliced_at_end_date = get_sliced_requests(filter_condition)
            expected_content = [2, 2, 0, 0, 0, 0, 0, 0, 0, 0]
            self.assertEqual(submitted_requests_sliced_at_end_date, expected_content)
