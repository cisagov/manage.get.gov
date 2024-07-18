from django.test import RequestFactory
from io import StringIO
from registrar.models.user_domain_role import UserDomainRole
from registrar.utility.csv_export import (
    DomainDataTypeUser,
    get_default_start_date,
)
from api.tests.common import less_console_noise_decorator
from .common import MockDb, MockEppLib, create_user


class ExportDataTestUserFacing(MockDb, MockEppLib):
    """Tests our data exports for users"""

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()

    def tearDown(self):
        super().tearDown()

    @less_console_noise_decorator
    def test_domain_data_type_user(self):
        """Shows security contacts, domain managers, so for the current user"""

        # Add security email information
        self.domain_1.name = "defaultsecurity.gov"
        self.domain_1.save()
        # Invoke setter
        self.domain_1.security_contact
        self.domain_2.security_contact
        self.domain_3.security_contact
        # Add a first ready date on the first domain. Leaving the others blank.
        self.domain_1.first_ready = get_default_start_date()
        self.domain_1.save()

        # Create a user and associate it with some domains
        user = create_user()
        UserDomainRole.objects.create(user=user, domain=self.domain_1)
        UserDomainRole.objects.create(user=user, domain=self.domain_2)

        # Create a request object
        request = self.factory.get("/")
        request.user = user

        # Create a CSV file in memory
        csv_file = StringIO()
        # Call the export functions
        DomainDataTypeUser.export_data_to_csv(csv_file, request=request)
        # Reset the CSV file's position to the beginning
        csv_file.seek(0)
        # Read the content into a variable
        csv_content = csv_file.read()

        # We expect only domains associated with the user
        expected_content = (
            "Domain name,Status,First ready on,Expiration date,Domain type,Agency,Organization name,"
            "City,State,SO,SO email,"
            "Security contact email,Domain managers,Invited domain managers\n"
            "defaultsecurity.gov,Ready,2023-11-01,(blank),Federal - Executive,World War I Centennial Commission,,,, ,,"
            '(blank),"meoward@rocks.com, info@example.com, big_lebowski@dude.co, staff@example.com",'
            "woofwardthethird@rocks.com\n"
            "adomain2.gov,Dns needed,(blank),(blank),Interstate,,,,, ,,(blank),"
            '"meoward@rocks.com, staff@example.com",squeaker@rocks.com\n'
        )

        # Normalize line endings and remove commas,
        # spaces and leading/trailing whitespace
        csv_content = csv_content.replace(",,", "").replace(",", "").replace(" ", "").replace("\r\n", "\n").strip()
        expected_content = expected_content.replace(",,", "").replace(",", "").replace(" ", "").strip()
        self.maxDiff = None
        self.assertEqual(csv_content, expected_content)
