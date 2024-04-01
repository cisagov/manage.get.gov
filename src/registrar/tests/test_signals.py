from django.test import TestCase
from django.contrib.auth import get_user_model

from registrar.models import Contact
from registrar.models.domain_request import DomainRequest
from registrar.tests.common import completed_domain_request


class TestUserPostSave(TestCase):
    def setUp(self):
        self.username = "test_user"
        self.first_name = "First"
        self.last_name = "Last"
        self.email = "info@example.com"
        self.phone = "202-555-0133"

        self.preferred_first_name = "One"
        self.preferred_last_name = "Two"
        self.preferred_email = "front_desk@example.com"
        self.preferred_phone = "202-555-0134"

    def test_user_created_without_matching_contact(self):
        """Expect 1 Contact containing data copied from User."""
        self.assertEqual(len(Contact.objects.all()), 0)
        user = get_user_model().objects.create(
            username=self.username,
            first_name=self.first_name,
            last_name=self.last_name,
            email=self.email,
            phone=self.phone,
        )
        actual = Contact.objects.get(user=user)
        self.assertEqual(actual.first_name, self.first_name)
        self.assertEqual(actual.last_name, self.last_name)
        self.assertEqual(actual.email, self.email)
        self.assertEqual(actual.phone, self.phone)

    def test_user_created_with_matching_contact(self):
        """Expect 1 Contact associated, but with no data copied from User."""
        self.assertEqual(len(Contact.objects.all()), 0)
        Contact.objects.create(
            first_name=self.preferred_first_name,
            last_name=self.preferred_last_name,
            email=self.email,  # must be the same, to find the match!
            phone=self.preferred_phone,
        )
        user = get_user_model().objects.create(
            username=self.username,
            first_name=self.first_name,
            last_name=self.last_name,
            email=self.email,
        )
        actual = Contact.objects.get(user=user)
        self.assertEqual(actual.first_name, self.preferred_first_name)
        self.assertEqual(actual.last_name, self.preferred_last_name)
        self.assertEqual(actual.email, self.email)
        self.assertEqual(actual.phone, self.preferred_phone)

    def test_user_updated_without_matching_contact(self):
        """Expect 1 Contact containing data copied from User."""
        # create the user
        self.assertEqual(len(Contact.objects.all()), 0)
        user = get_user_model().objects.create(username=self.username, first_name="", last_name="", email="", phone="")
        # delete the contact
        Contact.objects.all().delete()
        self.assertEqual(len(Contact.objects.all()), 0)
        # modify the user
        user.username = self.username
        user.first_name = self.first_name
        user.last_name = self.last_name
        user.email = self.email
        user.phone = self.phone
        user.save()
        # test
        actual = Contact.objects.get(user=user)
        self.assertEqual(actual.first_name, self.first_name)
        self.assertEqual(actual.last_name, self.last_name)
        self.assertEqual(actual.email, self.email)
        self.assertEqual(actual.phone, self.phone)

    def test_user_updated_with_matching_contact(self):
        """Expect 1 Contact associated, but with no data copied from User."""
        # create the user
        self.assertEqual(len(Contact.objects.all()), 0)
        user = get_user_model().objects.create(
            username=self.username,
            first_name=self.first_name,
            last_name=self.last_name,
            email=self.email,
            phone=self.phone,
        )
        # modify the user
        user.first_name = self.preferred_first_name
        user.last_name = self.preferred_last_name
        user.email = self.preferred_email
        user.phone = self.preferred_phone
        user.save()
        # test
        actual = Contact.objects.get(user=user)
        self.assertEqual(actual.first_name, self.first_name)
        self.assertEqual(actual.last_name, self.last_name)
        self.assertEqual(actual.email, self.email)
        self.assertEqual(actual.phone, self.phone)


class TestDomainRequestSignals(TestCase):
    """Tests hooked signals on the DomainRequest object"""

    def tearDown(self):
        DomainRequest.objects.all().delete()
        super().tearDown()

    def test_create_or_update_organization_type_new_instance(self):
        """Test create_or_update_organization_type when creating a new instance"""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=True,
        )

        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION)

    def test_create_or_update_organization_type_new_instance_federal_does_nothing(self):
        """Test if create_or_update_organization_type does nothing when creating a new instance for federal"""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.FEDERAL,
            is_election_board=True,
        )
        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.FEDERAL)

    def test_create_or_update_organization_type_existing_instance_updates_election_board(self):
        """Test create_or_update_organization_type for an existing instance."""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=False,
        )
        domain_request.is_election_board = True
        domain_request.save()

        self.assertEqual(domain_request.is_election_board, True)
        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION)

        # Try reverting the election board value
        domain_request.is_election_board = False
        domain_request.save()

        self.assertEqual(domain_request.is_election_board, False)
        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY)

        # Try reverting setting an invalid value for election board (should revert to False)
        domain_request.is_election_board = None
        domain_request.save()

        self.assertEqual(domain_request.is_election_board, False)
        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY)

    def test_create_or_update_organization_type_existing_instance_updates_generic_org_type(self):
        """Test create_or_update_organization_type when modifying generic_org_type on an existing instance."""
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=True,
        )

        domain_request.generic_org_type = DomainRequest.OrganizationChoices.INTERSTATE
        domain_request.save()

        # Election board should be None because interstate cannot have an election board.
        self.assertEqual(domain_request.is_election_board, None)
        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.INTERSTATE)

        # Try changing the org Type to something that CAN have an election board.
        domain_request_tribal = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="startedTribal.gov",
            generic_org_type=DomainRequest.OrganizationChoices.TRIBAL,
            is_election_board=True,
        )
        self.assertEqual(
            domain_request_tribal.organization_type, DomainRequest.OrgChoicesElectionOffice.TRIBAL_ELECTION
        )

        # Change the org type
        domain_request_tribal.generic_org_type = DomainRequest.OrganizationChoices.STATE_OR_TERRITORY
        domain_request_tribal.save()

        self.assertEqual(domain_request_tribal.is_election_board, True)
        self.assertEqual(
            domain_request_tribal.organization_type, DomainRequest.OrgChoicesElectionOffice.STATE_OR_TERRITORY_ELECTION
        )

    def test_create_or_update_organization_type_no_update(self):
        """Test create_or_update_organization_type when there are no values to update."""

        # Test for when both generic_org_type and organization_type is declared,
        # and are both non-election board
        domain_request = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="started.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=False,
        )
        domain_request.save()
        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY)
        self.assertEqual(domain_request.is_election_board, False)
        self.assertEqual(domain_request.generic_org_type, DomainRequest.OrganizationChoices.CITY)

        # Test for when both generic_org_type and organization_type is declared,
        # and are both election board
        domain_request_election = completed_domain_request(
            status=DomainRequest.DomainRequestStatus.STARTED,
            name="startedElection.gov",
            generic_org_type=DomainRequest.OrganizationChoices.CITY,
            is_election_board=True,
            organization_type=DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION,
        )

        self.assertEqual(
            domain_request_election.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION
        )
        self.assertEqual(domain_request_election.is_election_board, True)
        self.assertEqual(domain_request_election.generic_org_type, DomainRequest.OrganizationChoices.CITY)

        # Modify an unrelated existing value for both, and ensure that everything is still consistent
        domain_request.city = "Fudge"
        domain_request_election.city = "Caramel"
        domain_request.save()
        domain_request_election.save()

        self.assertEqual(domain_request.city, "Fudge")
        self.assertEqual(domain_request_election.city, "Caramel")

        # Test for non-election
        self.assertEqual(domain_request.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY)
        self.assertEqual(domain_request.is_election_board, False)
        self.assertEqual(domain_request.generic_org_type, DomainRequest.OrganizationChoices.CITY)

        # Test for election
        self.assertEqual(
            domain_request_election.organization_type, DomainRequest.OrgChoicesElectionOffice.CITY_ELECTION
        )
        self.assertEqual(domain_request_election.is_election_board, True)
        self.assertEqual(domain_request_election.generic_org_type, DomainRequest.OrganizationChoices.CITY)
