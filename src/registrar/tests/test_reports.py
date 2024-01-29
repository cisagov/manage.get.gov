import csv
import io
from django.test import Client, RequestFactory, TestCase
from io import StringIO
from registrar.models.domain_information import DomainInformation
from registrar.models.domain import Domain
from registrar.models.public_contact import PublicContact
from registrar.models.user import User
from django.contrib.auth import get_user_model
from registrar.tests.common import MockEppLib
from registrar.utility.csv_export import (
    write_header,
    write_body,
    get_default_start_date,
    get_default_end_date,
)
from django.core.management import call_command
from unittest.mock import MagicMock, call, mock_open, patch
from api.views import get_current_federal, get_current_full
from django.conf import settings
from botocore.exceptions import ClientError
import boto3_mocking
from registrar.utility.s3_bucket import S3ClientError, S3ClientErrorCodes  # type: ignore
from datetime import date, datetime, timedelta
from django.utils import timezone
from .common import less_console_noise

class CsvReportsTest(TestCase):
    """Tests to determine if we are uploading our reports correctly"""

    def setUp(self):
        """Create fake domain data"""
        self.client = Client(HTTP_HOST="localhost:8080")
        self.factory = RequestFactory()
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

    @boto3_mocking.patching
    def test_generate_federal_report(self):
        """Ensures that we correctly generate current-federal.csv"""
        with less_console_noise():
            mock_client = MagicMock()
            fake_open = mock_open()
            expected_file_content = [
                call("Domain name,Domain type,Agency,Organization name,City,State,Security contact email\r\n"),
                call("cdomain1.gov,Federal - Executive,World War I Centennial Commission,,,, \r\n"),
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
                call("cdomain1.gov,Federal - Executive,World War I Centennial Commission,,,, \r\n"),
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


class ExportDataTest(MockEppLib):
    def setUp(self):
        super().setUp()
        username = "test_user"
        first_name = "First"
        last_name = "Last"
        email = "info@example.com"
        self.user = get_user_model().objects.create(
            username=username, first_name=first_name, last_name=last_name, email=email
        )

        self.domain_1, _ = Domain.objects.get_or_create(
            name="cdomain1.gov", state=Domain.State.READY, first_ready=timezone.now()
        )
        self.domain_2, _ = Domain.objects.get_or_create(name="adomain2.gov", state=Domain.State.DNS_NEEDED)
        self.domain_3, _ = Domain.objects.get_or_create(name="ddomain3.gov", state=Domain.State.ON_HOLD)
        self.domain_4, _ = Domain.objects.get_or_create(name="bdomain4.gov", state=Domain.State.UNKNOWN)
        self.domain_4, _ = Domain.objects.get_or_create(name="bdomain4.gov", state=Domain.State.UNKNOWN)
        self.domain_5, _ = Domain.objects.get_or_create(
            name="bdomain5.gov", state=Domain.State.DELETED, deleted=timezone.make_aware(datetime(2023, 11, 1))
        )
        self.domain_6, _ = Domain.objects.get_or_create(
            name="bdomain6.gov", state=Domain.State.DELETED, deleted=timezone.make_aware(datetime(1980, 10, 16))
        )
        self.domain_7, _ = Domain.objects.get_or_create(
            name="xdomain7.gov", state=Domain.State.DELETED, deleted=timezone.now()
        )
        self.domain_8, _ = Domain.objects.get_or_create(
            name="sdomain8.gov", state=Domain.State.DELETED, deleted=timezone.now()
        )
        # We use timezone.make_aware to sync to server time a datetime object with the current date (using date.today())
        # and a specific time (using datetime.min.time()).
        # Deleted yesterday
        self.domain_9, _ = Domain.objects.get_or_create(
            name="zdomain9.gov",
            state=Domain.State.DELETED,
            deleted=timezone.make_aware(datetime.combine(date.today() - timedelta(days=1), datetime.min.time())),
        )
        # ready tomorrow
        self.domain_10, _ = Domain.objects.get_or_create(
            name="adomain10.gov",
            state=Domain.State.READY,
            first_ready=timezone.make_aware(datetime.combine(date.today() + timedelta(days=1), datetime.min.time())),
        )

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
        self.domain_information_5, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_5,
            organization_type="federal",
            federal_agency="Armed Forces Retirement Home",
        )
        self.domain_information_6, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_6,
            organization_type="federal",
            federal_agency="Armed Forces Retirement Home",
        )
        self.domain_information_7, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_7,
            organization_type="federal",
            federal_agency="Armed Forces Retirement Home",
        )
        self.domain_information_8, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_8,
            organization_type="federal",
            federal_agency="Armed Forces Retirement Home",
        )
        self.domain_information_9, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_9,
            organization_type="federal",
            federal_agency="Armed Forces Retirement Home",
        )
        self.domain_information_10, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_10,
            organization_type="federal",
            federal_agency="Armed Forces Retirement Home",
        )

    def tearDown(self):
        PublicContact.objects.all().delete()
        Domain.objects.all().delete()
        DomainInformation.objects.all().delete()
        User.objects.all().delete()
        super().tearDown()

    def test_export_domains_to_writer_security_emails(self):
        """Test that export_domains_to_writer returns the
        expected security email"""
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
            write_header(writer, columns)
            write_body(writer, columns, sort_fields, filter_condition)
            # Reset the CSV file's position to the beginning
            csv_file.seek(0)
            # Read the content into a variable
            csv_content = csv_file.read()
            # We expect READY domains,
            # sorted alphabetially by domain name
            expected_content = (
                "Domain name,Domain type,Agency,Organization name,City,State,AO,"
                "AO email,Security contact email,Status,Expiration date\n"
                "adomain10.gov,Federal,Armed Forces Retirement Home,Ready\n"
                "adomain2.gov,Interstate,(blank),Dns needed\n"
                "ddomain3.gov,Federal,Armed Forces Retirement Home,123@mail.gov,On hold,2023-05-25\n"
                "defaultsecurity.gov,Federal - Executive,World War I Centennial Commission,(blank),Ready"
            )
            # Normalize line endings and remove commas,
            # spaces and leading/trailing whitespace
            csv_content = csv_content.replace(",,", "").replace(",", "").replace(" ", "").replace("\r\n", "\n").strip()
            expected_content = expected_content.replace(",,", "").replace(",", "").replace(" ", "").strip()
            self.assertEqual(csv_content, expected_content)

    def test_write_body(self):
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
            write_header(writer, columns)
            write_body(writer, columns, sort_fields, filter_condition)
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
                "cdomain1.gov,Federal - Executive,World War I Centennial Commission,Ready\n"
                "ddomain3.gov,Federal,Armed Forces Retirement Home,On hold\n"
            )
            # Normalize line endings and remove commas,
            # spaces and leading/trailing whitespace
            csv_content = csv_content.replace(",,", "").replace(",", "").replace(" ", "").replace("\r\n", "\n").strip()
            expected_content = expected_content.replace(",,", "").replace(",", "").replace(" ", "").strip()
            self.assertEqual(csv_content, expected_content)

    def test_write_body_additional(self):
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
            sort_fields = ["domain__name", "federal_agency", "organization_type"]
            filter_condition = {
                "organization_type__icontains": "federal",
                "domain__state__in": [
                    Domain.State.READY,
                    Domain.State.DNS_NEEDED,
                    Domain.State.ON_HOLD,
                ],
            }
            # Call the export functions
            write_header(writer, columns)
            write_body(writer, columns, sort_fields, filter_condition)
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
                "cdomain1.gov,Federal - Executive,World War I Centennial Commission\n"
                "ddomain3.gov,Federal,Armed Forces Retirement Home\n"
            )
            # Normalize line endings and remove commas,
            # spaces and leading/trailing whitespace
            csv_content = csv_content.replace(",,", "").replace(",", "").replace(" ", "").replace("\r\n", "\n").strip()
            expected_content = expected_content.replace(",,", "").replace(",", "").replace(" ", "").strip()
            self.assertEqual(csv_content, expected_content)

    def test_write_body_with_date_filter_pulls_domains_in_range(self):
        """Test that domains that are
            1. READY and their first_ready dates are in range
            2. DELETED and their deleted dates are in range
        are pulled when the growth report conditions are applied to export_domains_to_writed.
        Test that ready domains are sorted by first_ready/deleted dates first, names second.

        We considered testing export_data_growth_to_csv which calls write_body
        and would have been easy to set up, but expected_content would contain created_at dates
        which are hard to mock.

        TODO: Simplify is created_at is not needed for the report."""
        with less_console_noise():
            # Create a CSV file in memory
            csv_file = StringIO()
            writer = csv.writer(csv_file)
            # We use timezone.make_aware to sync to server time a datetime object with the current date (using date.today())
            # and a specific time (using datetime.min.time()).
            end_date = timezone.make_aware(datetime.combine(date.today() + timedelta(days=2), datetime.min.time()))
            start_date = timezone.make_aware(datetime.combine(date.today() - timedelta(days=2), datetime.min.time()))

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
                "domain__first_ready__lte": end_date,
                "domain__first_ready__gte": start_date,
            }
            filter_conditions_for_deleted_domains = {
                "domain__state__in": [
                    Domain.State.DELETED,
                ],
                "domain__deleted__lte": end_date,
                "domain__deleted__gte": start_date,
            }

            # Call the export functions
            write_header(writer, columns)
            write_body(
                writer,
                columns,
                sort_fields,
                filter_condition,
            )
            write_body(
                writer,
                columns,
                sort_fields_for_deleted_domains,
                filter_conditions_for_deleted_domains,
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
                "zdomain9.gov,Federal,Armed Forces Retirement Home,,,,Deleted,\n"
                "sdomain8.gov,Federal,Armed Forces Retirement Home,,,,Deleted,\n"
                "xdomain7.gov,Federal,Armed Forces Retirement Home,,,,Deleted,\n"
            )

            # Normalize line endings and remove commas,
            # spaces and leading/trailing whitespace
            csv_content = csv_content.replace(",,", "").replace(",", "").replace(" ", "").replace("\r\n", "\n").strip()
            expected_content = expected_content.replace(",,", "").replace(",", "").replace(" ", "").strip()

            self.assertEqual(csv_content, expected_content)


class HelperFunctions(TestCase):
    """This asserts that 1=1. Its limited usefulness lies in making sure the helper methods stay healthy."""

    def test_get_default_start_date(self):
        expected_date = timezone.make_aware(datetime(2023, 11, 1))
        actual_date = get_default_start_date()
        self.assertEqual(actual_date, expected_date)

    def test_get_default_end_date(self):
        # Note: You may need to mock timezone.now() for accurate testing
        expected_date = timezone.now()
        actual_date = get_default_end_date()
        self.assertEqual(actual_date.date(), expected_date.date())
