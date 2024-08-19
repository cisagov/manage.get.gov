import copy
from datetime import date, datetime, time
from django.core.management import call_command
from django.test import TestCase, override_settings
from registrar.models.senior_official import SeniorOfficial
from registrar.utility.constants import BranchChoices
from django.utils import timezone
from django.utils.module_loading import import_string
import logging
import pyzipper
from registrar.management.commands.clean_tables import Command as CleanTablesCommand
from registrar.management.commands.export_tables import Command as ExportTablesCommand
from registrar.models import (
    User,
    Domain,
    DomainRequest,
    Contact,
    Website,
    DomainInvitation,
    TransitionDomain,
    DomainInformation,
    UserDomainRole,
    VerifiedByStaff,
    PublicContact,
    FederalAgency,
)
import tablib
from unittest.mock import patch, call, MagicMock, mock_open
from epplibwrapper import commands, common

from .common import MockEppLib, less_console_noise, completed_domain_request
from api.tests.common import less_console_noise_decorator

logger = logging.getLogger(__name__)


class TestPopulateVerificationType(MockEppLib):
    """Tests for the populate_organization_type script"""

    @less_console_noise_decorator
    def setUp(self):
        """Creates a fake domain object"""
        super().setUp()

        # Get the domain requests
        self.domain_request_1 = completed_domain_request(
            name="lasers.gov",
            generic_org_type=DomainRequest.OrganizationChoices.FEDERAL,
            is_election_board=True,
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
        )

        # Approve the request
        self.domain_request_1.approve()

        # Get the domains
        self.domain_1 = Domain.objects.get(name="lasers.gov")

        # Get users
        self.regular_user, _ = User.objects.get_or_create(username="testuser@igormail.gov")

        vip, _ = VerifiedByStaff.objects.get_or_create(email="vipuser@igormail.gov")
        self.verified_by_staff_user, _ = User.objects.get_or_create(username="vipuser@igormail.gov")

        grandfathered, _ = TransitionDomain.objects.get_or_create(
            username="grandpa@igormail.gov", domain_name=self.domain_1.name
        )
        self.grandfathered_user, _ = User.objects.get_or_create(username="grandpa@igormail.gov")

        invited, _ = DomainInvitation.objects.get_or_create(
            email="invited@igormail.gov", domain=self.domain_1, status=DomainInvitation.DomainInvitationStatus.RETRIEVED
        )
        self.invited_user, _ = User.objects.get_or_create(username="invited@igormail.gov")

        self.untouched_user, _ = User.objects.get_or_create(
            username="iaminvincible@igormail.gov", verification_type=User.VerificationTypeChoices.GRANDFATHERED
        )

        # Fixture users should be untouched by the script. These will auto update once the
        # user logs in / creates an account.
        self.fixture_user, _ = User.objects.get_or_create(
            username="fixture@igormail.gov", verification_type=User.VerificationTypeChoices.FIXTURE_USER
        )

    def tearDown(self):
        """Deletes all DB objects related to migrations"""
        super().tearDown()

        # Delete domains and related information
        Domain.objects.all().delete()
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        User.objects.all().delete()
        Contact.objects.all().delete()
        Website.objects.all().delete()

    @less_console_noise_decorator
    def run_populate_verification_type(self):
        """
        This method executes the populate_organization_type command.

        The 'call_command' function from Django's management framework is then used to
        execute the populate_organization_type command with the specified arguments.
        """
        with patch(
            "registrar.management.commands.utility.terminal_helper.TerminalHelper.query_yes_no_exit",  # noqa
            return_value=True,
        ):
            call_command("populate_verification_type")

    @less_console_noise_decorator
    def test_verification_type_script_populates_data(self):
        """Ensures that the verification type script actually populates data"""

        # Run the script
        self.run_populate_verification_type()

        # Scripts don't work as we'd expect in our test environment, we need to manually
        # trigger the refresh event
        self.regular_user.refresh_from_db()
        self.grandfathered_user.refresh_from_db()
        self.invited_user.refresh_from_db()
        self.verified_by_staff_user.refresh_from_db()
        self.untouched_user.refresh_from_db()

        # Test all users
        self.assertEqual(self.regular_user.verification_type, User.VerificationTypeChoices.REGULAR)
        self.assertEqual(self.grandfathered_user.verification_type, User.VerificationTypeChoices.GRANDFATHERED)
        self.assertEqual(self.invited_user.verification_type, User.VerificationTypeChoices.INVITED)
        self.assertEqual(self.verified_by_staff_user.verification_type, User.VerificationTypeChoices.VERIFIED_BY_STAFF)
        self.assertEqual(self.untouched_user.verification_type, User.VerificationTypeChoices.GRANDFATHERED)
        self.assertEqual(self.fixture_user.verification_type, User.VerificationTypeChoices.FIXTURE_USER)


class TestPopulateOrganizationType(MockEppLib):
    """Tests for the populate_organization_type script"""

    @less_console_noise_decorator
    def setUp(self):
        """Creates a fake domain object"""
        super().setUp()

        # Get the domain requests
        self.domain_request_1 = completed_domain_request(
            name="lasers.gov",
            generic_org_type=DomainRequest.OrganizationChoices.FEDERAL,
            is_election_board=True,
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
        )
        self.domain_request_2 = completed_domain_request(
            name="readysetgo.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
        )
        self.domain_request_3 = completed_domain_request(
            name="manualtransmission.gov",
            generic_org_type=DomainRequest.OrganizationChoices.TRIBAL,
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
        )
        self.domain_request_4 = completed_domain_request(
            name="saladandfries.gov",
            generic_org_type=DomainRequest.OrganizationChoices.TRIBAL,
            is_election_board=True,
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
        )

        # Approve all three requests
        self.domain_request_1.approve()
        self.domain_request_2.approve()
        self.domain_request_3.approve()
        self.domain_request_4.approve()

        # Get the domains
        self.domain_1 = Domain.objects.get(name="lasers.gov")
        self.domain_2 = Domain.objects.get(name="readysetgo.gov")
        self.domain_3 = Domain.objects.get(name="manualtransmission.gov")
        self.domain_4 = Domain.objects.get(name="saladandfries.gov")

        # Get the domain infos
        self.domain_info_1 = DomainInformation.objects.get(domain=self.domain_1)
        self.domain_info_2 = DomainInformation.objects.get(domain=self.domain_2)
        self.domain_info_3 = DomainInformation.objects.get(domain=self.domain_3)
        self.domain_info_4 = DomainInformation.objects.get(domain=self.domain_4)

    def tearDown(self):
        """Deletes all DB objects related to migrations"""
        super().tearDown()

        # Delete domains and related information
        Domain.objects.all().delete()
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        User.objects.all().delete()
        Contact.objects.all().delete()
        Website.objects.all().delete()

    @less_console_noise_decorator
    def run_populate_organization_type(self):
        """
        This method executes the populate_organization_type command.

        The 'call_command' function from Django's management framework is then used to
        execute the populate_organization_type command with the specified arguments.
        """
        with patch(
            "registrar.management.commands.utility.terminal_helper.TerminalHelper.query_yes_no_exit",  # noqa
            return_value=True,
        ):
            call_command("populate_organization_type", "registrar/tests/data/fake_election_domains.csv")

    @less_console_noise_decorator
    def assert_expected_org_values_on_request_and_info(
        self,
        domain_request: DomainRequest,
        domain_info: DomainInformation,
        expected_values: dict,
    ):
        """
        This is a helper function that tests the following conditions:
        1. DomainRequest and DomainInformation (on given objects) are equivalent
        2. That generic_org_type, is_election_board, and organization_type are equal to passed in values

        Args:
            domain_request (DomainRequest): The DomainRequest object to test

            domain_info (DomainInformation): The DomainInformation object to test

            expected_values (dict): Container for what we expect is_electionboard, generic_org_type,
            and organization_type to be on DomainRequest and DomainInformation.
                Example:
                expected_values = {
                    "is_election_board": False,
                    "generic_org_type": DomainRequest.OrganizationChoices.CITY,
                    "organization_type": DomainRequest.OrgChoicesElectionOffice.CITY,
                }
        """

        # Test domain request
        with self.subTest(field="DomainRequest"):
            self.assertEqual(domain_request.generic_org_type, expected_values["generic_org_type"])
            self.assertEqual(domain_request.is_election_board, expected_values["is_election_board"])
            self.assertEqual(domain_request.organization_type, expected_values["organization_type"])

        # Test domain info
        with self.subTest(field="DomainInformation"):
            self.assertEqual(domain_info.generic_org_type, expected_values["generic_org_type"])
            self.assertEqual(domain_info.is_election_board, expected_values["is_election_board"])
            self.assertEqual(domain_info.organization_type, expected_values["organization_type"])

    def do_nothing(self):
        """Does nothing for mocking purposes"""
        pass

    @less_console_noise_decorator
    def test_request_and_info_city_not_in_csv(self):
        """
        Tests what happens to a city domain that is not defined in the CSV.

        Scenario: A domain request (of type city) is made that is not defined in the CSV file.
            When a domain request is made for a city that is not listed in the CSV,
            Then the `is_election_board` value should remain False,
                and the `generic_org_type` and `organization_type` should both be `city`.

        Expected Result: The `is_election_board` and `generic_org_type` attributes should be unchanged.
        The `organization_type` field should now be `city`.
        """

        city_request = self.domain_request_2
        city_info = self.domain_request_2

        # Make sure that all data is correct before proceeding.
        # Since the presave fixture is in effect, we should expect that
        # is_election_board is equal to none, even though we tried to define it as "True"
        expected_values = {
            "is_election_board": False,
            "generic_org_type": DomainRequest.OrganizationChoices.CITY,
            "organization_type": DomainRequest.OrgChoicesElectionOffice.CITY,
        }
        self.assert_expected_org_values_on_request_and_info(city_request, city_info, expected_values)

        # Run the populate script
        try:
            self.run_populate_organization_type()
        except Exception as e:
            self.fail(f"Could not run populate_organization_type script. Failed with exception: {e}")

        # All values should be the same
        self.assert_expected_org_values_on_request_and_info(city_request, city_info, expected_values)

    @less_console_noise_decorator
    def test_request_and_info_federal(self):
        """
        Tests what happens to a federal domain after the script is run (should be unchanged).

        Scenario: A domain request (of type federal) is processed after running the populate_organization_type script.
            When a federal domain request is made,
            Then the `is_election_board` value should remain None,
                and the `generic_org_type` and `organization_type` fields should both be `federal`.

        Expected Result: The `is_election_board` and `generic_org_type` attributes should be unchanged.
        The `organization_type` field should now be `federal`.
        """
        federal_request = self.domain_request_1
        federal_info = self.domain_info_1

        # Make sure that all data is correct before proceeding.
        # Since the presave fixture is in effect, we should expect that
        # is_election_board is equal to none, even though we tried to define it as "True"
        expected_values = {
            "is_election_board": None,
            "generic_org_type": DomainRequest.OrganizationChoices.FEDERAL,
            "organization_type": DomainRequest.OrgChoicesElectionOffice.FEDERAL,
        }
        self.assert_expected_org_values_on_request_and_info(federal_request, federal_info, expected_values)

        # Run the populate script
        try:
            self.run_populate_organization_type()
        except Exception as e:
            self.fail(f"Could not run populate_organization_type script. Failed with exception: {e}")

        # All values should be the same
        self.assert_expected_org_values_on_request_and_info(federal_request, federal_info, expected_values)

    @less_console_noise_decorator
    def test_request_and_info_tribal_add_election_office(self):
        """
        Tests if a tribal domain in the election csv changes organization_type to TRIBAL - ELECTION
        for the domain request and the domain info
        """

        # Set org type fields to none to mimic an environment without this data
        tribal_request = self.domain_request_3
        tribal_request.organization_type = None
        tribal_info = self.domain_info_3
        tribal_info.organization_type = None
        with patch.object(DomainRequest, "sync_organization_type", self.do_nothing):
            with patch.object(DomainInformation, "sync_organization_type", self.do_nothing):
                tribal_request.save()
                tribal_info.save()

        # Make sure that all data is correct before proceeding.
        expected_values = {
            "is_election_board": False,
            "generic_org_type": DomainRequest.OrganizationChoices.TRIBAL,
            "organization_type": None,
        }
        self.assert_expected_org_values_on_request_and_info(tribal_request, tribal_info, expected_values)

        # Run the populate script
        try:
            self.run_populate_organization_type()
        except Exception as e:
            self.fail(f"Could not run populate_organization_type script. Failed with exception: {e}")

        tribal_request.refresh_from_db()
        tribal_info.refresh_from_db()

        # Because we define this in the "csv", we expect that is election board will switch to True,
        # and organization_type will now be tribal_election
        expected_values["is_election_board"] = True
        expected_values["organization_type"] = DomainRequest.OrgChoicesElectionOffice.TRIBAL_ELECTION

        self.assert_expected_org_values_on_request_and_info(tribal_request, tribal_info, expected_values)

    @less_console_noise_decorator
    def test_request_and_info_tribal_doesnt_remove_election_office(self):
        """
        Tests if a tribal domain in the election csv changes organization_type to TRIBAL_ELECTION
        when the is_election_board is True, and generic_org_type is Tribal when it is not
        present in the CSV.

        To avoid overwriting data, the script should not set any domain specified as
        an election_office (that doesn't exist in the CSV) to false.
        """

        # Set org type fields to none to mimic an environment without this data
        tribal_election_request = self.domain_request_4
        tribal_election_info = self.domain_info_4
        tribal_election_request.organization_type = None
        tribal_election_info.organization_type = None
        with patch.object(DomainRequest, "sync_organization_type", self.do_nothing):
            with patch.object(DomainInformation, "sync_organization_type", self.do_nothing):
                tribal_election_request.save()
                tribal_election_info.save()

        # Make sure that all data is correct before proceeding.
        # Because the presave fixture is in place when creating this, we should expect that the
        # organization_type variable is already pre-populated. We will test what happens when
        # it is not in another test.
        expected_values = {
            "is_election_board": True,
            "generic_org_type": DomainRequest.OrganizationChoices.TRIBAL,
            "organization_type": None,
        }
        self.assert_expected_org_values_on_request_and_info(
            tribal_election_request, tribal_election_info, expected_values
        )

        # Run the populate script
        try:
            self.run_populate_organization_type()
        except Exception as e:
            self.fail(f"Could not run populate_organization_type script. Failed with exception: {e}")

        # If we don't define this in the "csv", but the value was already true,
        # we expect that is election board will stay True, and the org type will be tribal,
        # and organization_type will now be tribal_election
        expected_values["organization_type"] = DomainRequest.OrgChoicesElectionOffice.TRIBAL_ELECTION
        tribal_election_request.refresh_from_db()
        tribal_election_info.refresh_from_db()
        self.assert_expected_org_values_on_request_and_info(
            tribal_election_request, tribal_election_info, expected_values
        )


class TestPopulateFirstReady(TestCase):
    """Tests for the populate_first_ready script"""

    @less_console_noise_decorator
    def setUp(self):
        """Creates a fake domain object"""
        super().setUp()
        self.ready_domain, _ = Domain.objects.get_or_create(name="fakeready.gov", state=Domain.State.READY)
        self.dns_needed_domain, _ = Domain.objects.get_or_create(name="fakedns.gov", state=Domain.State.DNS_NEEDED)
        self.deleted_domain, _ = Domain.objects.get_or_create(name="fakedeleted.gov", state=Domain.State.DELETED)
        self.hold_domain, _ = Domain.objects.get_or_create(name="fakehold.gov", state=Domain.State.ON_HOLD)
        self.unknown_domain, _ = Domain.objects.get_or_create(name="fakeunknown.gov", state=Domain.State.UNKNOWN)

        # Set a ready_at date for testing purposes
        self.ready_at_date = date(2022, 12, 31)
        _ready_at_datetime = datetime.combine(self.ready_at_date, time.min)
        self.ready_at_date_tz_aware = timezone.make_aware(_ready_at_datetime, timezone=timezone.utc)

    def tearDown(self):
        """Deletes all DB objects related to migrations"""
        super().tearDown()

        # Delete domains
        Domain.objects.all().delete()

    def run_populate_first_ready(self):
        """
        This method executes the populate_first_ready command.

        The 'call_command' function from Django's management framework is then used to
        execute the populate_first_ready command with the specified arguments.
        """
        with less_console_noise():
            with patch(
                "registrar.management.commands.utility.terminal_helper.TerminalHelper.query_yes_no_exit",  # noqa
                return_value=True,
            ):
                call_command("populate_first_ready")

    def test_populate_first_ready_state_ready(self):
        """
        Tests that the populate_first_ready works as expected for the state 'ready'
        """
        with less_console_noise():
            # Set the created at date
            self.ready_domain.created_at = self.ready_at_date_tz_aware
            self.ready_domain.save()
            desired_domain = copy.deepcopy(self.ready_domain)
            desired_domain.first_ready = self.ready_at_date
            # Run the expiration date script
            self.run_populate_first_ready()
            self.assertEqual(desired_domain, self.ready_domain)
            # Explicitly test the first_ready date
            first_ready = Domain.objects.filter(name="fakeready.gov").get().first_ready
            self.assertEqual(first_ready, self.ready_at_date)

    def test_populate_first_ready_state_deleted(self):
        """
        Tests that the populate_first_ready works as expected for the state 'deleted'
        """
        with less_console_noise():
            # Set the created at date
            self.deleted_domain.created_at = self.ready_at_date_tz_aware
            self.deleted_domain.save()
            desired_domain = copy.deepcopy(self.deleted_domain)
            desired_domain.first_ready = self.ready_at_date
            # Run the expiration date script
            self.run_populate_first_ready()
            self.assertEqual(desired_domain, self.deleted_domain)
            # Explicitly test the first_ready date
            first_ready = Domain.objects.filter(name="fakedeleted.gov").get().first_ready
            self.assertEqual(first_ready, self.ready_at_date)

    def test_populate_first_ready_state_dns_needed(self):
        """
        Tests that the populate_first_ready doesn't make changes when a domain's state  is 'dns_needed'
        """
        with less_console_noise():
            # Set the created at date
            self.dns_needed_domain.created_at = self.ready_at_date_tz_aware
            self.dns_needed_domain.save()
            desired_domain = copy.deepcopy(self.dns_needed_domain)
            desired_domain.first_ready = None
            # Run the expiration date script
            self.run_populate_first_ready()
            current_domain = self.dns_needed_domain
            # The object should largely be unaltered (does not test first_ready)
            self.assertEqual(desired_domain, current_domain)
            first_ready = Domain.objects.filter(name="fakedns.gov").get().first_ready
            # Explicitly test the first_ready date
            self.assertNotEqual(first_ready, self.ready_at_date)
            self.assertEqual(first_ready, None)

    def test_populate_first_ready_state_on_hold(self):
        """
        Tests that the populate_first_ready works as expected for the state 'on_hold'
        """
        with less_console_noise():
            self.hold_domain.created_at = self.ready_at_date_tz_aware
            self.hold_domain.save()
            desired_domain = copy.deepcopy(self.hold_domain)
            desired_domain.first_ready = self.ready_at_date
            # Run the update first ready_at script
            self.run_populate_first_ready()
            current_domain = self.hold_domain
            self.assertEqual(desired_domain, current_domain)
            # Explicitly test the first_ready date
            first_ready = Domain.objects.filter(name="fakehold.gov").get().first_ready
            self.assertEqual(first_ready, self.ready_at_date)

    def test_populate_first_ready_state_unknown(self):
        """
        Tests that the populate_first_ready works as expected for the state 'unknown'
        """
        with less_console_noise():
            # Set the created at date
            self.unknown_domain.created_at = self.ready_at_date_tz_aware
            self.unknown_domain.save()
            desired_domain = copy.deepcopy(self.unknown_domain)
            desired_domain.first_ready = None
            # Run the expiration date script
            self.run_populate_first_ready()
            current_domain = self.unknown_domain
            # The object should largely be unaltered (does not test first_ready)
            self.assertEqual(desired_domain, current_domain)
            # Explicitly test the first_ready date
            first_ready = Domain.objects.filter(name="fakeunknown.gov").get().first_ready
            self.assertNotEqual(first_ready, self.ready_at_date)
            self.assertEqual(first_ready, None)


class TestPatchAgencyInfo(TestCase):
    @less_console_noise_decorator
    def setUp(self):
        self.user, _ = User.objects.get_or_create(username="testuser")
        self.domain, _ = Domain.objects.get_or_create(name="testdomain.gov")
        self.domain_info, _ = DomainInformation.objects.get_or_create(domain=self.domain, creator=self.user)
        self.federal_agency, _ = FederalAgency.objects.get_or_create(agency="test agency")
        self.transition_domain, _ = TransitionDomain.objects.get_or_create(
            domain_name="testdomain.gov", federal_agency=self.federal_agency
        )

    def tearDown(self):
        Domain.objects.all().delete()
        DomainInformation.objects.all().delete()
        User.objects.all().delete()
        TransitionDomain.objects.all().delete()

    @patch("registrar.management.commands.utility.terminal_helper.TerminalHelper.query_yes_no_exit", return_value=True)
    def call_patch_federal_agency_info(self, mock_prompt):
        """Calls the patch_federal_agency_info command and mimics a keypress"""
        with less_console_noise():
            call_command("patch_federal_agency_info", "registrar/tests/data/fake_current_full.csv", debug=True)


class TestExtendExpirationDates(MockEppLib):
    @less_console_noise_decorator
    def setUp(self):
        """Defines the file name of migration_json and the folder its contained in"""
        super().setUp()
        # Create a valid domain that is updatable
        Domain.objects.get_or_create(
            name="waterbutpurple.gov", state=Domain.State.READY, expiration_date=date(2023, 11, 15)
        )
        TransitionDomain.objects.get_or_create(
            username="testytester@mail.com",
            domain_name="waterbutpurple.gov",
            epp_expiration_date=date(2023, 11, 15),
        )
        # Create a domain with an invalid expiration date
        Domain.objects.get_or_create(name="fake.gov", state=Domain.State.READY, expiration_date=date(2022, 5, 25))
        TransitionDomain.objects.get_or_create(
            username="themoonisactuallycheese@mail.com",
            domain_name="fake.gov",
            epp_expiration_date=date(2022, 5, 25),
        )
        # Create a domain with an invalid state
        Domain.objects.get_or_create(
            name="fakeneeded.gov", state=Domain.State.DNS_NEEDED, expiration_date=date(2023, 11, 15)
        )
        TransitionDomain.objects.get_or_create(
            username="fakeneeded@mail.com",
            domain_name="fakeneeded.gov",
            epp_expiration_date=date(2023, 11, 15),
        )
        # Create a domain with a date greater than the maximum
        Domain.objects.get_or_create(
            name="fakemaximum.gov", state=Domain.State.READY, expiration_date=date(2024, 12, 31)
        )
        TransitionDomain.objects.get_or_create(
            username="fakemaximum@mail.com",
            domain_name="fakemaximum.gov",
            epp_expiration_date=date(2024, 12, 31),
        )

    def tearDown(self):
        """Deletes all DB objects related to migrations"""
        super().tearDown()
        # Delete domain information
        Domain.objects.all().delete()
        DomainInformation.objects.all().delete()
        DomainInvitation.objects.all().delete()
        TransitionDomain.objects.all().delete()

        # Delete users
        User.objects.all().delete()
        UserDomainRole.objects.all().delete()

    def run_extend_expiration_dates(self):
        """
        This method executes the extend_expiration_dates command.

        The 'call_command' function from Django's management framework is then used to
        execute the extend_expiration_dates command with the specified arguments.
        """
        with less_console_noise():
            with patch(
                "registrar.management.commands.utility.terminal_helper.TerminalHelper.query_yes_no_exit",  # noqa
                return_value=True,
            ):
                call_command("extend_expiration_dates")

    def test_extends_expiration_date_correctly(self):
        """
        Tests that the extend_expiration_dates method extends dates as expected
        """
        with less_console_noise():
            desired_domain = Domain.objects.filter(name="waterbutpurple.gov").get()
            desired_domain.expiration_date = date(2024, 11, 15)
            # Run the expiration date script
            self.run_extend_expiration_dates()
            current_domain = Domain.objects.filter(name="waterbutpurple.gov").get()
            self.assertEqual(desired_domain, current_domain)
            # Explicitly test the expiration date
            self.assertEqual(current_domain.expiration_date, date(2024, 11, 15))

    def test_extends_expiration_date_skips_non_current(self):
        """
        Tests that the extend_expiration_dates method correctly skips domains
        with an expiration date less than a certain threshold.
        """
        with less_console_noise():
            desired_domain = Domain.objects.filter(name="fake.gov").get()
            desired_domain.expiration_date = date(2022, 5, 25)
            # Run the expiration date script
            self.run_extend_expiration_dates()
            current_domain = Domain.objects.filter(name="fake.gov").get()
            self.assertEqual(desired_domain, current_domain)
            # Explicitly test the expiration date. The extend_expiration_dates script
            # will skip all dates less than date(2023, 11, 15), meaning that this domain
            # should not be affected by the change.
            self.assertEqual(current_domain.expiration_date, date(2022, 5, 25))

    def test_extends_expiration_date_skips_maximum_date(self):
        """
        Tests that the extend_expiration_dates method correctly skips domains
        with an expiration date more than a certain threshold.
        """
        with less_console_noise():
            desired_domain = Domain.objects.filter(name="fakemaximum.gov").get()
            desired_domain.expiration_date = date(2024, 12, 31)

            # Run the expiration date script
            self.run_extend_expiration_dates()

            current_domain = Domain.objects.filter(name="fakemaximum.gov").get()
            self.assertEqual(desired_domain, current_domain)

            # Explicitly test the expiration date. The extend_expiration_dates script
            # will skip all dates less than date(2023, 11, 15), meaning that this domain
            # should not be affected by the change.
            self.assertEqual(current_domain.expiration_date, date(2024, 12, 31))

    def test_extends_expiration_date_skips_non_ready(self):
        """
        Tests that the extend_expiration_dates method correctly skips domains not in the state "ready"
        """
        with less_console_noise():
            desired_domain = Domain.objects.filter(name="fakeneeded.gov").get()
            desired_domain.expiration_date = date(2023, 11, 15)

            # Run the expiration date script
            self.run_extend_expiration_dates()

            current_domain = Domain.objects.filter(name="fakeneeded.gov").get()
            self.assertEqual(desired_domain, current_domain)

            # Explicitly test the expiration date. The extend_expiration_dates script
            # will skip all dates less than date(2023, 11, 15), meaning that this domain
            # should not be affected by the change.
            self.assertEqual(current_domain.expiration_date, date(2023, 11, 15))

    def test_extends_expiration_date_idempotent(self):
        """
        Tests the idempotency of the extend_expiration_dates command.

        Verifies that running the method multiple times does not change the expiration date
        of a domain beyond the initial extension.
        """
        with less_console_noise():
            desired_domain = Domain.objects.filter(name="waterbutpurple.gov").get()
            desired_domain.expiration_date = date(2024, 11, 15)
            # Run the expiration date script
            self.run_extend_expiration_dates()
            current_domain = Domain.objects.filter(name="waterbutpurple.gov").get()
            self.assertEqual(desired_domain, current_domain)
            # Explicitly test the expiration date
            self.assertEqual(desired_domain.expiration_date, date(2024, 11, 15))
            # Run the expiration date script again
            self.run_extend_expiration_dates()
            # The old domain shouldn't have changed
            self.assertEqual(desired_domain, current_domain)
            # Explicitly test the expiration date - should be the same
            self.assertEqual(desired_domain.expiration_date, date(2024, 11, 15))


class TestDiscloseEmails(MockEppLib):
    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()
        PublicContact.objects.all().delete()
        Domain.objects.all().delete()

    def run_disclose_security_emails(self):
        """
        This method executes the disclose_security_emails command.

        The 'call_command' function from Django's management framework is then used to
        execute the disclose_security_emails command.
        """
        with less_console_noise():
            with patch(
                "registrar.management.commands.utility.terminal_helper.TerminalHelper.query_yes_no_exit",  # noqa
                return_value=True,
            ):
                call_command("disclose_security_emails")

    def test_disclose_security_emails(self):
        """
        Tests that command disclose_security_emails runs successfully with
        appropriate EPP calll to UpdateContact.
        """
        with less_console_noise():
            domain, _ = Domain.objects.get_or_create(name="testdisclose.gov", state=Domain.State.READY)
            expectedSecContact = PublicContact.get_default_security()
            expectedSecContact.domain = domain
            expectedSecContact.email = "123@mail.gov"
            # set domain security email to 123@mail.gov instead of default email
            domain.security_contact = expectedSecContact
            self.run_disclose_security_emails()

            # running disclose_security_emails sends EPP call UpdateContact with disclose
            self.mockedSendFunction.assert_has_calls(
                [
                    call(
                        commands.UpdateContact(
                            id=domain.security_contact.registry_id,
                            postal_info=domain._make_epp_contact_postal_info(contact=domain.security_contact),
                            email=domain.security_contact.email,
                            voice=domain.security_contact.voice,
                            fax=domain.security_contact.fax,
                            auth_info=common.ContactAuthInfo(pw="2fooBAR123fooBaz"),
                            disclose=domain._disclose_fields(contact=domain.security_contact),
                        ),
                        cleaned=True,
                    )
                ]
            )


class TestCleanTables(TestCase):
    """Test the clean_tables script"""

    def setUp(self):
        self.command = CleanTablesCommand()
        self.logger_patcher = patch("registrar.management.commands.clean_tables.logger")
        self.logger_mock = self.logger_patcher.start()

    def tearDown(self):
        self.logger_patcher.stop()

    @override_settings(IS_PRODUCTION=True)
    def test_command_logs_error_in_production(self):
        """Test that the handle method does not process in production"""
        with less_console_noise():
            with patch(
                "registrar.management.commands.utility.terminal_helper.TerminalHelper.query_yes_no_exit",  # noqa
                return_value=True,
            ):
                call_command("clean_tables")
                self.logger_mock.error.assert_called_with("clean_tables cannot be run in production")

    @override_settings(IS_PRODUCTION=False)
    def test_command_cleans_tables(self):
        """test that the handle method functions properly to clean tables"""

        with patch("django.apps.apps.get_model") as get_model_mock:
            model_mock = MagicMock()
            get_model_mock.return_value = model_mock

            with patch(
                "registrar.management.commands.utility.terminal_helper.TerminalHelper.query_yes_no_exit",  # noqa
                return_value=True,
            ):

                # List of pks to be returned in batches, one list for each of 11 tables
                pk_batch = [1, 2, 3, 4, 5, 6]
                # Create a list of batches with alternating non-empty and empty lists
                pk_batches = [pk_batch, []] * 11

                # Set the side effect of values_list to return different pk batches
                # First time values_list is called it returns list of 6 objects to delete;
                # Next time values_list is called it returns empty list
                def values_list_side_effect(*args, **kwargs):
                    if args == ("pk",) and kwargs.get("flat", False):
                        return pk_batches.pop(0)
                    return []

                model_mock.objects.values_list.side_effect = values_list_side_effect
                # Mock the return value of `delete()` to be (6, ...)
                model_mock.objects.filter.return_value.delete.return_value = (6, None)

                call_command("clean_tables")

                table_names = [
                    "DomainInformation",
                    "DomainRequest",
                    "FederalAgency",
                    "PublicContact",
                    "HostIp",
                    "Host",
                    "Domain",
                    "User",
                    "Contact",
                    "Website",
                    "DraftDomain",
                ]

                expected_filter_calls = [call(pk__in=[1, 2, 3, 4, 5, 6]) for _ in range(11)]

                actual_filter_calls = [c for c in model_mock.objects.filter.call_args_list if "pk__in" in c[1]]

                try:
                    # Assert that filter(pk__in=...) was called with expected arguments
                    self.assertEqual(actual_filter_calls, expected_filter_calls)

                    # Check that delete() was called for each batch
                    for batch in [[1, 2, 3, 4, 5, 6]]:
                        model_mock.objects.filter(pk__in=batch).delete.assert_called()

                    for table_name in table_names:
                        get_model_mock.assert_any_call("registrar", table_name)
                        self.logger_mock.info.assert_any_call(
                            f"Successfully cleaned table {table_name}, deleted 6 rows"
                        )
                except AssertionError as e:
                    print(f"AssertionError: {e}")
                    raise

    @override_settings(IS_PRODUCTION=False)
    def test_command_handles_nonexistent_model(self):
        """Test that exceptions for non existent models are handled properly within the handle method"""
        with less_console_noise():
            with patch("django.apps.apps.get_model", side_effect=LookupError):
                with patch(
                    "registrar.management.commands.utility.terminal_helper.TerminalHelper.query_yes_no_exit",  # noqa
                    return_value=True,
                ):
                    call_command("clean_tables")
                    # Assert that the error message was logged for any of the table names
                    self.logger_mock.error.assert_any_call("Model for table DomainInformation not found.")
                    self.logger_mock.error.assert_any_call("Model for table DomainRequest not found.")
                    self.logger_mock.error.assert_any_call("Model for table PublicContact not found.")
                    self.logger_mock.error.assert_any_call("Model for table Domain not found.")
                    self.logger_mock.error.assert_any_call("Model for table User not found.")
                    self.logger_mock.error.assert_any_call("Model for table Contact not found.")
                    self.logger_mock.error.assert_any_call("Model for table Website not found.")
                    self.logger_mock.error.assert_any_call("Model for table DraftDomain not found.")
                    self.logger_mock.error.assert_any_call("Model for table HostIp not found.")
                    self.logger_mock.error.assert_any_call("Model for table Host not found.")

    @override_settings(IS_PRODUCTION=False)
    def test_command_logs_other_exceptions(self):
        """Test that generic exceptions are handled properly in the handle method"""
        with less_console_noise():
            with patch("django.apps.apps.get_model") as get_model_mock:
                model_mock = MagicMock()
                get_model_mock.return_value = model_mock

                # Mock the values_list so that DomainInformation attempts a delete
                pk_batches = [[1, 2, 3, 4, 5, 6], []]

                def values_list_side_effect(*args, **kwargs):
                    if args == ("pk",) and kwargs.get("flat", False):
                        return pk_batches.pop(0)
                    return []

                model_mock.objects.values_list.side_effect = values_list_side_effect

                # Mock delete to raise a generic exception
                model_mock.objects.filter.return_value.delete.side_effect = Exception("Mocked delete exception")

                with patch(
                    "registrar.management.commands.utility.terminal_helper.TerminalHelper.query_yes_no_exit",
                    return_value=True,
                ):
                    with self.assertRaises(Exception) as context:
                        # Execute the command
                        call_command("clean_tables")

                        # Check the exception message
                        self.assertEqual(str(context.exception), "Custom delete error")

                        # Assert that delete was called
                        model_mock.objects.filter.return_value.delete.assert_called()


class TestExportTables(MockEppLib):
    """Test the export_tables script"""

    def setUp(self):
        self.command = ExportTablesCommand()
        self.logger_patcher = patch("registrar.management.commands.export_tables.logger")
        self.logger_mock = self.logger_patcher.start()

    def tearDown(self):
        self.logger_patcher.stop()

    @less_console_noise_decorator
    @patch("os.makedirs")
    @patch("os.path.exists")
    @patch("os.remove")
    @patch("pyzipper.AESZipFile")
    @patch("registrar.management.commands.export_tables.getattr")
    @patch("builtins.open", new_callable=mock_open)
    @patch("os.listdir")
    def test_handle(
        self, mock_listdir, mock_open, mock_getattr, mock_zipfile, mock_remove, mock_path_exists, mock_makedirs
    ):
        """test that the handle method properly exports tables"""
        # Mock os.makedirs to do nothing
        mock_makedirs.return_value = None

        # Mock os.path.exists to always return True
        mock_path_exists.return_value = True

        # Check that the export_table function was called for each table
        table_names = [
            "User",
            "Contact",
            "Domain",
            "DomainRequest",
            "DomainInformation",
            "FederalAgency",
            "UserDomainRole",
            "DraftDomain",
            "Website",
            "HostIp",
            "Host",
            "PublicContact",
        ]

        # Mock directory listing
        mock_listdir.side_effect = lambda path: [f"{table}_1.csv" for table in table_names]

        # Mock the resource class and its export method
        mock_dataset = tablib.Dataset()
        mock_dataset.headers = ["header1", "header2"]
        mock_dataset.append(["row1_col1", "row1_col2"])
        mock_resource_class = MagicMock()
        mock_resource_class().export.return_value = mock_dataset
        mock_getattr.return_value = mock_resource_class

        command_instance = ExportTablesCommand()
        command_instance.handle()

        # Check that os.makedirs was called once to create the tmp directory
        mock_makedirs.assert_called_once_with("tmp", exist_ok=True)

        # Check that the CSV file was written
        for table_name in table_names:
            # Check that os.remove was called
            mock_remove.assert_any_call(f"tmp/{table_name}_1.csv")

        # Check that the zipfile was created and files were added
        mock_zipfile.assert_called_once_with("tmp/exported_tables.zip", "w", compression=pyzipper.ZIP_DEFLATED)
        zipfile_instance = mock_zipfile.return_value.__enter__.return_value
        for table_name in table_names:
            zipfile_instance.write.assert_any_call(f"tmp/{table_name}_1.csv", f"{table_name}_1.csv")

        # Verify logging for added files
        for table_name in table_names:
            self.logger_mock.info.assert_any_call(f"Added {table_name}_1.csv to tmp/exported_files.zip")

        # Verify logging for removed files
        for table_name in table_names:
            self.logger_mock.info.assert_any_call(f"Removed {table_name}_1.csv")

    @patch("registrar.management.commands.export_tables.getattr")
    def test_export_table_handles_missing_resource_class(self, mock_getattr):
        """Test that missing resource classes are handled properly in the handle method"""
        with less_console_noise():
            mock_getattr.side_effect = AttributeError

            # Import the command to avoid any locale or gettext issues
            command_class = import_string("registrar.management.commands.export_tables.Command")
            command_instance = command_class()
            command_instance.export_table("NonExistentTable")

            self.logger_mock.error.assert_called_with(
                "Resource class NonExistentTableResource not found in registrar.admin"
            )

    @patch("registrar.management.commands.export_tables.getattr")
    def test_export_table_handles_generic_exception(self, mock_getattr):
        """Test that general exceptions in the handle method are handled correctly"""
        with less_console_noise():
            mock_resource_class = MagicMock()
            mock_resource_class().export.side_effect = Exception("Test Exception")
            mock_getattr.return_value = mock_resource_class

            # Import the command to avoid any locale or gettext issues
            command_class = import_string("registrar.management.commands.export_tables.Command")
            command_instance = command_class()
            command_instance.export_table("TestTable")

            self.logger_mock.error.assert_called_with("Failed to export TestTable: Test Exception")


class TestImportTables(TestCase):
    """Test the import_tables script"""

    @patch("registrar.management.commands.import_tables.os.makedirs")
    @patch("registrar.management.commands.import_tables.os.path.exists")
    @patch("registrar.management.commands.import_tables.os.remove")
    @patch("registrar.management.commands.import_tables.pyzipper.AESZipFile")
    @patch("registrar.management.commands.import_tables.tablib.Dataset")
    @patch("registrar.management.commands.import_tables.open", create=True)
    @patch("registrar.management.commands.import_tables.logger")
    @patch("registrar.management.commands.import_tables.getattr")
    @patch("django.apps.apps.get_model")
    @patch("os.listdir")
    def test_handle(
        self,
        mock_listdir,
        mock_get_model,
        mock_getattr,
        mock_logger,
        mock_open,
        mock_dataset,
        mock_zipfile,
        mock_remove,
        mock_path_exists,
        mock_makedirs,
    ):
        """Test that the handle method properly imports tables"""
        with less_console_noise():
            # Mock os.makedirs to do nothing
            mock_makedirs.return_value = None

            # Mock os.path.exists to always return True
            mock_path_exists.return_value = True

            # Mock the zipfile to have extractall return None
            mock_zipfile_instance = mock_zipfile.return_value.__enter__.return_value
            mock_zipfile_instance.extractall.return_value = None

            # Check that the import_table function was called for each table
            table_names = [
                "User",
                "Contact",
                "Domain",
                "DomainRequest",
                "DomainInformation",
                "UserDomainRole",
                "DraftDomain",
                "Website",
                "HostIp",
                "Host",
                "PublicContact",
            ]

            # Mock directory listing
            mock_listdir.side_effect = lambda path: [f"{table}_1.csv" for table in table_names]

            # Mock the CSV file content
            csv_content = b"mock_csv_data"

            # Mock the open function to return a mock file
            mock_open.return_value.__enter__.return_value.read.return_value = csv_content

            # Mock the Dataset class and its load method to return a dataset
            mock_dataset_instance = MagicMock(spec=tablib.Dataset)
            with patch(
                "registrar.management.commands.import_tables.tablib.Dataset.load", return_value=mock_dataset_instance
            ):
                # Mock the resource class and its import method
                mock_resource_class = MagicMock()
                mock_resource_instance = MagicMock()
                mock_result = MagicMock()
                mock_result.has_errors.return_value = False
                mock_resource_instance.import_data.return_value = mock_result
                mock_resource_class.return_value = mock_resource_instance
                mock_getattr.return_value = mock_resource_class

                # Call the command
                call_command("import_tables")

                # Check that os.makedirs was called once to create the tmp directory
                mock_makedirs.assert_called_once_with("tmp", exist_ok=True)

                # Check that os.path.exists was called once for the zip file
                mock_path_exists.assert_any_call("tmp/exported_tables.zip")

                # Check that pyzipper.AESZipFile was called once to open the zip file
                mock_zipfile.assert_called_once_with("tmp/exported_tables.zip", "r")

                # Check that extractall was called once to extract the zip file contents
                mock_zipfile_instance.extractall.assert_called_once_with("tmp")

                # Check that os.path.exists was called for each table
                for table_name in table_names:
                    mock_path_exists.assert_any_call(f"{table_name}_1.csv")

                # Check that logger.info was called for each successful import
                for table_name in table_names:
                    mock_logger.info.assert_any_call(f"Successfully imported {table_name}_1.csv into {table_name}")

                # Check that logger.error was not called for resource class not found
                mock_logger.error.assert_not_called()

                # Check that os.remove was called for each CSV file
                for table_name in table_names:
                    mock_remove.assert_any_call(f"{table_name}_1.csv")

                # Check that logger.info was called for each CSV file removal
                for table_name in table_names:
                    mock_logger.info.assert_any_call(f"Removed temporary file {table_name}_1.csv")

    @patch("registrar.management.commands.import_tables.logger")
    @patch("registrar.management.commands.import_tables.os.makedirs")
    @patch("registrar.management.commands.import_tables.os.path.exists")
    def test_handle_zip_file_not_found(self, mock_path_exists, mock_makedirs, mock_logger):
        """Test the handle method when the zip file doesn't exist"""
        with less_console_noise():
            # Mock os.makedirs to do nothing
            mock_makedirs.return_value = None

            # Mock os.path.exists to return False
            mock_path_exists.return_value = False

            call_command("import_tables")

            # Check that logger.error was called with the correct message
            mock_logger.error.assert_called_once_with("Zip file tmp/exported_tables.zip does not exist.")


class TestTransferFederalAgencyType(TestCase):
    """Tests for the transfer_federal_agency_type script"""

    @less_console_noise_decorator
    def setUp(self):
        """Creates a fake domain object"""
        super().setUp()

        self.amtrak, _ = FederalAgency.objects.get_or_create(agency="AMTRAK")
        self.legislative_branch, _ = FederalAgency.objects.get_or_create(agency="Legislative Branch")
        self.library_of_congress, _ = FederalAgency.objects.get_or_create(agency="Library of Congress")
        self.gov_admin, _ = FederalAgency.objects.get_or_create(agency="gov Administration")

        self.domain_request_1 = completed_domain_request(
            name="testgov.gov",
            federal_agency=self.amtrak,
            federal_type=BranchChoices.EXECUTIVE,
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
        )
        self.domain_request_2 = completed_domain_request(
            name="cheesefactory.gov",
            federal_agency=self.legislative_branch,
            federal_type=BranchChoices.LEGISLATIVE,
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
        )
        self.domain_request_3 = completed_domain_request(
            name="meowardslaw.gov",
            federal_agency=self.library_of_congress,
            federal_type=BranchChoices.JUDICIAL,
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
        )

        # Duplicate fields with invalid data - we expect to skip updating these
        self.domain_request_4 = completed_domain_request(
            name="baddata.gov",
            federal_agency=self.gov_admin,
            federal_type=BranchChoices.EXECUTIVE,
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
        )
        self.domain_request_5 = completed_domain_request(
            name="worsedata.gov",
            federal_agency=self.gov_admin,
            federal_type=BranchChoices.JUDICIAL,
            status=DomainRequest.DomainRequestStatus.IN_REVIEW,
        )

        self.domain_request_1.approve()
        self.domain_request_2.approve()
        self.domain_request_3.approve()
        self.domain_request_4.approve()
        self.domain_request_5.approve()

    def tearDown(self):
        """Deletes all DB objects related to migrations"""
        super().tearDown()

        # Delete domains and related information
        Domain.objects.all().delete()
        DomainInformation.objects.all().delete()
        DomainRequest.objects.all().delete()
        User.objects.all().delete()
        Contact.objects.all().delete()
        Website.objects.all().delete()
        FederalAgency.objects.filter(
            id__in=[self.amtrak.id, self.legislative_branch.id, self.library_of_congress.id, self.gov_admin.id]
        ).delete()

    def run_transfer_federal_agency_type(self):
        """
        This method executes the transfer_federal_agency_type command.

        The 'call_command' function from Django's management framework is then used to
        execute the populate_first_ready command with the specified arguments.
        """
        with less_console_noise():
            with patch(
                "registrar.management.commands.utility.terminal_helper.TerminalHelper.query_yes_no_exit",  # noqa
                return_value=True,
            ):
                call_command("transfer_federal_agency_type")

    @less_console_noise_decorator
    def test_transfer_federal_agency_type_script(self):
        """
        Tests that the transfer_federal_agency_type script updates what we expect, and skips what we expect
        """

        # Before proceeding, make sure we don't have any data contamination
        tested_agencies = [
            self.amtrak,
            self.legislative_branch,
            self.library_of_congress,
            self.gov_admin,
        ]
        for agency in tested_agencies:
            self.assertEqual(agency.federal_type, None)

        # Run the script
        self.run_transfer_federal_agency_type()

        # Refresh the local db instance to reflect changes
        self.amtrak.refresh_from_db()
        self.legislative_branch.refresh_from_db()
        self.library_of_congress.refresh_from_db()
        self.gov_admin.refresh_from_db()

        # Test the values that we expect to be updated
        self.assertEqual(self.amtrak.federal_type, BranchChoices.EXECUTIVE)
        self.assertEqual(self.legislative_branch.federal_type, BranchChoices.LEGISLATIVE)
        self.assertEqual(self.library_of_congress.federal_type, BranchChoices.JUDICIAL)

        # We don't expect this field to be updated (as it has duplicate data)
        self.assertEqual(self.gov_admin.federal_type, None)


class TestLoadSeniorOfficialTable(TestCase):
    def setUp(self):
        super().setUp()
        self.csv_path = "registrar/tests/data/fake_federal_cio.csv"

    def tearDown(self):
        super().tearDown()
        SeniorOfficial.objects.all().delete()
        FederalAgency.objects.all().delete()

    @less_console_noise_decorator
    def run_load_senior_official_table(self):
        with patch(
            "registrar.management.commands.utility.terminal_helper.TerminalHelper.query_yes_no_exit",
            return_value=True,
        ):
            call_command("load_senior_official_table", self.csv_path)

    @less_console_noise_decorator
    def test_load_senior_official_table(self):
        """Ensures that running the senior official script creates the data we expect"""
        # Get test FederalAgency objects
        abmc, _ = FederalAgency.objects.get_or_create(agency="American Battle Monuments Commission")
        achp, _ = FederalAgency.objects.get_or_create(agency="Advisory Council on Historic Preservation")

        # run the script
        self.run_load_senior_official_table()

        # Check the data returned by the script
        jan_uary = SeniorOfficial.objects.get(first_name="Jan", last_name="Uary")
        self.assertEqual(jan_uary.title, "CIO")
        self.assertEqual(jan_uary.email, "fakemrfake@igorville.gov")
        self.assertEqual(jan_uary.federal_agency, abmc)

        reggie_ronald = SeniorOfficial.objects.get(first_name="Reggie", last_name="Ronald")
        self.assertEqual(reggie_ronald.title, "CIO")
        self.assertEqual(reggie_ronald.email, "reggie.ronald@igorville.gov")
        self.assertEqual(reggie_ronald.federal_agency, achp)

        # Two should be created in total
        self.assertEqual(SeniorOfficial.objects.count(), 2)

    @less_console_noise_decorator
    def test_load_senior_official_table_duplicate_entry(self):
        """Ensures that duplicate data won't be created"""
        # Create a SeniorOfficial that matches one in the CSV
        abmc, _ = FederalAgency.objects.get_or_create(agency="American Battle Monuments Commission")
        SeniorOfficial.objects.create(
            first_name="Jan", last_name="Uary", title="CIO", email="fakemrfake@igorville.gov", federal_agency=abmc
        )

        self.assertEqual(SeniorOfficial.objects.count(), 1)

        # run the script
        self.run_load_senior_official_table()

        # Check if only one new SeniorOfficial object was created
        self.assertEqual(SeniorOfficial.objects.count(), 2)


class TestPopulateFederalAgencyInitialsAndFceb(TestCase):
    def setUp(self):
        self.csv_path = "registrar/tests/data/fake_federal_cio.csv"

        # Create test FederalAgency objects
        self.agency1, _ = FederalAgency.objects.get_or_create(agency="American Battle Monuments Commission")
        self.agency2, _ = FederalAgency.objects.get_or_create(agency="Advisory Council on Historic Preservation")
        self.agency3, _ = FederalAgency.objects.get_or_create(agency="AMTRAK")
        self.agency4, _ = FederalAgency.objects.get_or_create(agency="John F. Kennedy Center for Performing Arts")

    def tearDown(self):
        SeniorOfficial.objects.all().delete()
        FederalAgency.objects.all().delete()

    @less_console_noise_decorator
    def run_populate_federal_agency_initials_and_fceb(self):
        with patch(
            "registrar.management.commands.utility.terminal_helper.TerminalHelper.query_yes_no_exit",
            return_value=True,
        ):
            call_command("populate_federal_agency_initials_and_fceb", self.csv_path)

    @less_console_noise_decorator
    def test_populate_federal_agency_initials_and_fceb(self):
        """Ensures that the script generates the data we want"""
        self.run_populate_federal_agency_initials_and_fceb()

        # Refresh the objects from the database
        self.agency1.refresh_from_db()
        self.agency2.refresh_from_db()
        self.agency3.refresh_from_db()
        self.agency4.refresh_from_db()

        # Check if FederalAgency objects were updated correctly
        self.assertEqual(self.agency1.initials, "ABMC")
        self.assertTrue(self.agency1.is_fceb)

        self.assertEqual(self.agency2.initials, "ACHP")
        self.assertTrue(self.agency2.is_fceb)

        # We expect that this field doesn't have any data,
        # as none is specified in the CSV
        self.assertIsNone(self.agency3.initials)
        self.assertIsNone(self.agency3.is_fceb)

        self.assertEqual(self.agency4.initials, "KC")
        self.assertFalse(self.agency4.is_fceb)

    @less_console_noise_decorator
    def test_populate_federal_agency_initials_and_fceb_missing_agency(self):
        """A test to ensure that the script doesn't modify unrelated fields"""
        # Add a FederalAgency that's not in the CSV
        missing_agency = FederalAgency.objects.create(agency="Missing Agency")

        self.run_populate_federal_agency_initials_and_fceb()

        # Verify that the missing agency was not updated
        missing_agency.refresh_from_db()
        self.assertIsNone(missing_agency.initials)
        self.assertIsNone(missing_agency.is_fceb)
