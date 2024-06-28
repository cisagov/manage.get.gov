import io
from django.test import Client, RequestFactory
from io import StringIO
from registrar.models.domain_request import DomainRequest
from registrar.models.domain import Domain
from registrar.utility.csv_export import (
    DomainDataFull,
    DomainDataType,
    DomainDataFederal,
    DomainGrowth,
    DomainManaged,
    DomainUnmanaged,
    DomainExport,
    DomainRequestExport,
    DomainRequestGrowth,
    DomainRequestDataFull,
    get_default_start_date,
    get_default_end_date,
)
from django.db.models import Case, When
from django.core.management import call_command
from unittest.mock import MagicMock, call, mock_open, patch
from api.views import get_current_federal, get_current_full
from django.conf import settings
from botocore.exceptions import ClientError
import boto3_mocking
from registrar.utility.s3_bucket import S3ClientError, S3ClientErrorCodes  # type: ignore
from django.utils import timezone
from api.tests.common import less_console_noise_decorator
from .common import MockDb, MockEppLib, less_console_noise, get_time_aware_date


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
                call("cdomain11.gov,Federal - Executive,World War I Centennial Commission,,,,\r\n"),
                call("cdomain1.gov,Federal - Executive,World War I Centennial Commission,,,,\r\n"),
                call("adomain10.gov,Federal,Armed Forces Retirement Home,,,,\r\n"),
                call("ddomain3.gov,Federal,Armed Forces Retirement Home,,,,\r\n"),
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
                call("cdomain11.gov,Federal - Executive,World War I Centennial Commission,,,,\r\n"),
                call("cdomain1.gov,Federal - Executive,World War I Centennial Commission,,,,\r\n"),
                call("adomain10.gov,Federal,Armed Forces Retirement Home,,,,\r\n"),
                call("ddomain3.gov,Federal,Armed Forces Retirement Home,,,,\r\n"),
                call("adomain2.gov,Interstate,,,,,\r\n"),
                call("zdomain12.gov,Interstate,,,,,\r\n"),
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

    @less_console_noise_decorator
    def test_domain_data_type(self):
        """Shows security contacts, domain managers, ao"""
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
        # Call the export functions
        DomainDataType.export_data_to_csv(csv_file)
        # Reset the CSV file's position to the beginning
        csv_file.seek(0)
        # Read the content into a variable
        csv_content = csv_file.read()
        # We expect READY domains,
        # sorted alphabetially by domain name
        expected_content = (
            "Domain name,Status,First ready on,Expiration date,Domain type,Agency,Organization name,City,State,AO,"
            "AO email,Security contact email,Domain managers,Invited domain managers\n"
            "cdomain11.gov,Ready,2024-04-02,(blank),Federal - Executive,World War I Centennial Commission,,,, ,,,"
            "meoward@rocks.com,\n"
            "defaultsecurity.gov,Ready,2023-11-01,(blank),Federal - Executive,World War I Centennial Commission,,,"
            ', ,,dotgov@cisa.dhs.gov,"meoward@rocks.com, info@example.com, big_lebowski@dude.co",'
            "woofwardthethird@rocks.com\n"
            "adomain10.gov,Ready,2024-04-03,(blank),Federal,Armed Forces Retirement Home,,,, ,,,,"
            "squeaker@rocks.com\n"
            "bdomain4.gov,Unknown,(blank),(blank),Federal,Armed Forces Retirement Home,,,, ,,,,\n"
            "bdomain5.gov,Deleted,(blank),(blank),Federal,Armed Forces Retirement Home,,,, ,,,,\n"
            "bdomain6.gov,Deleted,(blank),(blank),Federal,Armed Forces Retirement Home,,,, ,,,,\n"
            "ddomain3.gov,On hold,(blank),2023-11-15,Federal,Armed Forces Retirement Home,,,, ,,"
            "security@mail.gov,,\n"
            "sdomain8.gov,Deleted,(blank),(blank),Federal,Armed Forces Retirement Home,,,, ,,,,\n"
            "xdomain7.gov,Deleted,(blank),(blank),Federal,Armed Forces Retirement Home,,,, ,,,,\n"
            "zdomain9.gov,Deleted,(blank),(blank),Federal,Armed Forces Retirement Home,,,, ,,,,\n"
            "adomain2.gov,Dns needed,(blank),(blank),Interstate,,,,, ,,registrar@dotgov.gov,"
            "meoward@rocks.com,squeaker@rocks.com\n"
            "zdomain12.gov,Ready,2024-04-02,(blank),Interstate,,,,, ,,,meoward@rocks.com,\n"
        )
        # Normalize line endings and remove commas,
        # spaces and leading/trailing whitespace
        csv_content = csv_content.replace(",,", "").replace(",", "").replace(" ", "").replace("\r\n", "\n").strip()
        expected_content = expected_content.replace(",,", "").replace(",", "").replace(" ", "").strip()
        self.assertEqual(csv_content, expected_content)

    @less_console_noise_decorator
    def test_domain_data_full(self):
        """Shows security contacts, filtered by state"""
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
        # Call the export functions
        DomainDataFull.export_data_to_csv(csv_file)
        # Reset the CSV file's position to the beginning
        csv_file.seek(0)
        # Read the content into a variable
        csv_content = csv_file.read()
        # We expect READY domains,
        # sorted alphabetially by domain name
        expected_content = (
            "Domain name,Domain type,Agency,Organization name,City,State,Security contact email\n"
            "cdomain11.gov,Federal - Executive,World War I Centennial Commission,,,,\n"
            "defaultsecurity.gov,Federal - Executive,World War I Centennial Commission,,,,dotgov@cisa.dhs.gov\n"
            "adomain10.gov,Federal,Armed Forces Retirement Home,,,,\n"
            "ddomain3.gov,Federal,Armed Forces Retirement Home,,,,security@mail.gov\n"
            "adomain2.gov,Interstate,,,,,registrar@dotgov.gov\n"
            "zdomain12.gov,Interstate,,,,,\n"
        )
        # Normalize line endings and remove commas,
        # spaces and leading/trailing whitespace
        csv_content = csv_content.replace(",,", "").replace(",", "").replace(" ", "").replace("\r\n", "\n").strip()
        expected_content = expected_content.replace(",,", "").replace(",", "").replace(" ", "").strip()
        self.assertEqual(csv_content, expected_content)

    @less_console_noise_decorator
    def test_domain_data_federal(self):
        """Shows security contacts, filtered by state and org type"""
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
        # Call the export functions
        DomainDataFederal.export_data_to_csv(csv_file)
        # Reset the CSV file's position to the beginning
        csv_file.seek(0)
        # Read the content into a variable
        csv_content = csv_file.read()
        # We expect READY domains,
        # sorted alphabetially by domain name
        expected_content = (
            "Domain name,Domain type,Agency,Organization name,City,State,Security contact email\n"
            "cdomain11.gov,Federal - Executive,World War I Centennial Commission,,,,\n"
            "defaultsecurity.gov,Federal - Executive,World War I Centennial Commission,,,,dotgov@cisa.dhs.gov\n"
            "adomain10.gov,Federal,Armed Forces Retirement Home,,,,\n"
            "ddomain3.gov,Federal,Armed Forces Retirement Home,,,,security@mail.gov\n"
        )
        # Normalize line endings and remove commas,
        # spaces and leading/trailing whitespace
        csv_content = csv_content.replace(",,", "").replace(",", "").replace(" ", "").replace("\r\n", "\n").strip()
        expected_content = expected_content.replace(",,", "").replace(",", "").replace(" ", "").strip()
        self.assertEqual(csv_content, expected_content)

    @less_console_noise_decorator
    def test_domain_growth(self):
        """Shows ready and deleted domains within a date range, sorted"""
        # Remove "Created at" and "First ready" because we can't guess this immutable, dynamically generated test data
        columns = [
            "Domain name",
            "Domain type",
            "Agency",
            "Organization name",
            "City",
            "State",
            "Status",
            "Expiration date",
            # "Created at",
            # "First ready",
            "Deleted",
        ]
        sort = {
            "custom_sort": Case(
                When(domain__state=Domain.State.READY, then="domain__created_at"),
                When(domain__state=Domain.State.DELETED, then="domain__deleted"),
            )
        }
        with patch("registrar.utility.csv_export.DomainGrowth.get_columns", return_value=columns):
            with patch("registrar.utility.csv_export.DomainGrowth.get_annotations_for_sort", return_value=sort):
                # Create a CSV file in memory
                csv_file = StringIO()
                # Call the export functions
                DomainGrowth.export_data_to_csv(
                    csv_file,
                    self.start_date.strftime("%Y-%m-%d"),
                    self.end_date.strftime("%Y-%m-%d"),
                )
                # Reset the CSV file's position to the beginning
                csv_file.seek(0)
                # Read the content into a variable
                csv_content = csv_file.read()
                # We expect READY domains first, created between day-2 and day+2, sorted by created_at then name
                # and DELETED domains deleted between day-2 and day+2, sorted by deleted then name
                expected_content = (
                    "Domain name,Domain type,Agency,Organization name,City,"
                    "State,Status,Expiration date, Deleted\n"
                    "cdomain1.gov,Federal-Executive,World War I Centennial Commission,,,,Ready,(blank)\n"
                    "adomain10.gov,Federal,Armed Forces Retirement Home,,,,Ready,(blank)\n"
                    "cdomain11.govFederal-ExecutiveWorldWarICentennialCommissionReady(blank)\n"
                    "zdomain12.govInterstateReady(blank)\n"
                    "zdomain9.gov,Federal,ArmedForcesRetirementHome,Deleted,(blank),2024-04-01\n"
                    "sdomain8.gov,Federal,Armed Forces Retirement Home,,,,Deleted,(blank),2024-04-02\n"
                    "xdomain7.gov,FederalArmedForcesRetirementHome,Deleted,(blank),2024-04-02\n"
                )
                # Normalize line endings and remove commas,
                # spaces and leading/trailing whitespace
                csv_content = (
                    csv_content.replace(",,", "").replace(",", "").replace(" ", "").replace("\r\n", "\n").strip()
                )
                expected_content = expected_content.replace(",,", "").replace(",", "").replace(" ", "").strip()
                self.assertEqual(csv_content, expected_content)

    @less_console_noise_decorator
    def test_domain_managed(self):
        """Shows ready and deleted domains by an end date, sorted

        An invited user, woofwardthethird, should also be pulled into this report.

        squeaker@rocks.com is invited to domain2 (DNS_NEEDED) and domain10 (No managers).
        She should show twice in this report but not in test_DomainManaged."""
        # Create a CSV file in memory
        csv_file = StringIO()
        # Call the export functions
        DomainManaged.export_data_to_csv(
            csv_file,
            self.start_date.strftime("%Y-%m-%d"),
            self.end_date.strftime("%Y-%m-%d"),
        )
        # Reset the CSV file's position to the beginning
        csv_file.seek(0)
        # Read the content into a variable
        csv_content = csv_file.read()
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
            "Domain name,Domain type,Domain managers,Invited domain managers\n"
            "cdomain11.gov,Federal - Executive,meoward@rocks.com,\n"
            'cdomain1.gov,Federal - Executive,"meoward@rocks.com, info@example.com, big_lebowski@dude.co",'
            "woofwardthethird@rocks.com\n"
            "zdomain12.gov,Interstate,meoward@rocks.com,\n"
        )
        # Normalize line endings and remove commas,
        # spaces and leading/trailing whitespace
        csv_content = csv_content.replace(",,", "").replace(",", "").replace(" ", "").replace("\r\n", "\n").strip()
        expected_content = expected_content.replace(",,", "").replace(",", "").replace(" ", "").strip()
        self.assertEqual(csv_content, expected_content)

    @less_console_noise_decorator
    def test_domain_unmanaged(self):
        """Shows unmanaged domains by an end date, sorted"""
        # Create a CSV file in memory
        csv_file = StringIO()
        DomainUnmanaged.export_data_to_csv(
            csv_file, self.start_date.strftime("%Y-%m-%d"), self.end_date.strftime("%Y-%m-%d")
        )

        # Reset the CSV file's position to the beginning
        csv_file.seek(0)
        # Read the content into a variable
        csv_content = csv_file.read()

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

    @less_console_noise_decorator
    def test_domain_request_growth(self):
        """Shows submitted requests within a date range, sorted"""
        # Remove "Submitted at" because we can't guess this immutable, dynamically generated test data
        columns = [
            "Domain request",
            "Domain type",
            "Federal type",
            # "Submitted at",
        ]
        with patch("registrar.utility.csv_export.DomainRequestGrowth.get_columns", return_value=columns):
            # Create a CSV file in memory
            csv_file = StringIO()
            # Call the export functions
            DomainRequestGrowth.export_data_to_csv(
                csv_file,
                self.start_date.strftime("%Y-%m-%d"),
                self.end_date.strftime("%Y-%m-%d"),
            )
            # Reset the CSV file's position to the beginning
            csv_file.seek(0)
            # Read the content into a variable
            csv_content = csv_file.read()
            expected_content = (
                "Domain request,Domain type,Federal type\n"
                "city3.gov,Federal,Executive\n"
                "city4.gov,City,Executive\n"
                "city6.gov,Federal,Executive\n"
            )

            # Normalize line endings and remove commas,
            # spaces and leading/trailing whitespace
            csv_content = csv_content.replace(",,", "").replace(",", "").replace(" ", "").replace("\r\n", "\n").strip()
            expected_content = expected_content.replace(",,", "").replace(",", "").replace(" ", "").strip()

            self.assertEqual(csv_content, expected_content)

    @less_console_noise_decorator
    def test_domain_request_data_full(self):
        """Tests the full domain request report."""
        # Remove "Submitted at" because we can't guess this immutable, dynamically generated test data
        columns = [
            "Domain request",
            # "Submitted at",
            "Status",
            "Domain type",
            "Federal type",
            "Federal agency",
            "Organization name",
            "Election office",
            "City",
            "State/territory",
            "Region",
            "Creator first name",
            "Creator last name",
            "Creator email",
            "Creator approved domains count",
            "Creator active requests count",
            "Alternative domains",
            "AO first name",
            "AO last name",
            "AO email",
            "AO title/role",
            "Request purpose",
            "Request additional details",
            "Other contacts",
            "CISA regional representative",
            "Current websites",
            "Investigator",
        ]
        with patch("registrar.utility.csv_export.DomainRequestDataFull.get_columns", return_value=columns):
            # Create a CSV file in memory
            csv_file = StringIO()
            # Call the export functions
            DomainRequestDataFull.export_data_to_csv(csv_file)
            # Reset the CSV file's position to the beginning
            csv_file.seek(0)
            # Read the content into a variable
            csv_content = csv_file.read()
            print(csv_content)
            expected_content = (
                # Header
                "Domain request,Status,Domain type,Federal type,"
                "Federal agency,Organization name,Election office,City,State/territory,"
                "Region,Creator first name,Creator last name,Creator email,Creator approved domains count,"
                "Creator active requests count,Alternative domains,AO first name,AO last name,AO email,"
                "AO title/role,Request purpose,Request additional details,Other contacts,"
                "CISA regional representative,Current websites,Investigator\n"
                # Content
                "city5.gov,,Approved,Federal,Executive,,Testorg,N/A,,NY,2,,,,1,0,city1.gov,Testy,Tester,testy@town.com,"
                "Chief Tester,Purpose of the site,There is more,Testy Tester testy2@town.com,,city.com,\n"
                "city2.gov,,In review,Federal,Executive,,Testorg,N/A,,NY,2,,,,0,1,city1.gov,Testy,Tester,"
                "testy@town.com,"
                "Chief Tester,Purpose of the site,There is more,Testy Tester testy2@town.com,,city.com,\n"
                'city3.gov,Submitted,Federal,Executive,,Testorg,N/A,,NY,2,,,,0,1,"cheeseville.gov, city1.gov,'
                'igorville.gov",Testy,Tester,testy@town.com,Chief Tester,Purpose of the site,CISA-first-name '
                "CISA-last-name "
                '| There is more,"Meow Tester24 te2@town.com, Testy1232 Tester24 te2@town.com, Testy Tester '
                'testy2@town.com"'
                ',test@igorville.com,"city.com, https://www.example2.com, https://www.example.com",\n'
                "city4.gov,Submitted,City,Executive,,Testorg,Yes,,NY,2,,,,0,1,city1.gov,Testy,Tester,testy@town.com,"
                "Chief Tester,Purpose of the site,CISA-first-name CISA-last-name | There is more,Testy Tester "
                "testy2@town.com"
                ",cisaRep@igorville.gov,city.com,\n"
                "city6.gov,Submitted,Federal,Executive,,Testorg,N/A,,NY,2,,,,0,1,city1.gov,Testy,Tester,testy@town.com,"
                "Chief Tester,Purpose of the site,CISA-first-name CISA-last-name | There is more,Testy Tester "
                "testy2@town.com,"
                "cisaRep@igorville.gov,city.com,\n"
            )
            # Normalize line endings and remove commas,
            # spaces and leading/trailing whitespace
            csv_content = csv_content.replace(",,", "").replace(",", "").replace(" ", "").replace("\r\n", "\n").strip()
            expected_content = expected_content.replace(",,", "").replace(",", "").replace(" ", "").strip()
            self.assertEqual(csv_content, expected_content)


class HelperFunctions(MockDb):
    """This asserts that 1=1. Its limited usefulness lies in making sure the helper methods stay healthy."""

    def test_get_default_start_date(self):
        expected_date = get_time_aware_date()
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
            managed_domains_sliced_at_end_date = DomainExport.get_sliced_domains(filter_condition)
            expected_content = [3, 2, 1, 0, 0, 0, 0, 0, 0, 0]
            self.assertEqual(managed_domains_sliced_at_end_date, expected_content)

            # Test without distinct
            managed_domains_sliced_at_end_date = DomainExport.get_sliced_domains(filter_condition)
            expected_content = [3, 2, 1, 0, 0, 0, 0, 0, 0, 0]
            self.assertEqual(managed_domains_sliced_at_end_date, expected_content)

    def test_get_sliced_requests(self):
        """Should get fitered requests counts sliced by org type and election office."""

        with less_console_noise():
            filter_condition = {
                "status": DomainRequest.DomainRequestStatus.SUBMITTED,
                "submission_date__lte": self.end_date,
            }
            submitted_requests_sliced_at_end_date = DomainRequestExport.get_sliced_requests(filter_condition)
            expected_content = [3, 2, 0, 0, 0, 0, 1, 0, 0, 1]
            self.assertEqual(submitted_requests_sliced_at_end_date, expected_content)
