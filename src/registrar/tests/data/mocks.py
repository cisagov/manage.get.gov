from django.test import TestCase
from django.contrib.auth import get_user_model
from api.tests.common import less_console_noise
from registrar.models.domain_application import DomainApplication
from registrar.models.domain_information import DomainInformation
from registrar.models.domain import Domain
from registrar.models.user_domain_role import UserDomainRole
from registrar.models.public_contact import PublicContact
from registrar.models.user import User
from datetime import date, datetime, timedelta
from django.utils import timezone
from registrar.tests.common import MockEppLib, completed_application

class MockDb(MockEppLib):
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
            is_election_board=True
        )
        self.domain_information_2, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_2,
            organization_type="interstate",
            is_election_board=True
        )
        self.domain_information_3, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_3,
            organization_type="federal",
            federal_agency="Armed Forces Retirement Home",
            is_election_board=True
        )
        self.domain_information_4, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_4,
            organization_type="federal",
            federal_agency="Armed Forces Retirement Home",
            is_election_board=True
        )
        self.domain_information_5, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_5,
            organization_type="federal",
            federal_agency="Armed Forces Retirement Home",
            is_election_board=False
        )
        self.domain_information_6, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_6,
            organization_type="federal",
            federal_agency="Armed Forces Retirement Home",
            is_election_board=False
        )
        self.domain_information_7, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_7,
            organization_type="federal",
            federal_agency="Armed Forces Retirement Home",
            is_election_board=False
        )
        self.domain_information_8, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_8,
            organization_type="federal",
            federal_agency="Armed Forces Retirement Home",
            is_election_board=False
        )
        self.domain_information_9, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_9,
            organization_type="federal",
            federal_agency="Armed Forces Retirement Home",
            is_election_board=False
        )
        self.domain_information_10, _ = DomainInformation.objects.get_or_create(
            creator=self.user,
            domain=self.domain_10,
            organization_type="federal",
            federal_agency="Armed Forces Retirement Home",
            is_election_board=False
        )

        meoward_user = get_user_model().objects.create(
            username="meoward_username", first_name="first_meoward", last_name="last_meoward", email="meoward@rocks.com"
        )

        lebowski_user = get_user_model().objects.create(
            username="big_lebowski", first_name="big", last_name="lebowski", email="big_lebowski@dude.co"
        )

        # Test for more than 1 domain manager
        _, created = UserDomainRole.objects.get_or_create(
            user=meoward_user, domain=self.domain_1, role=UserDomainRole.Roles.MANAGER
        )

        _, created = UserDomainRole.objects.get_or_create(
            user=self.user, domain=self.domain_1, role=UserDomainRole.Roles.MANAGER
        )

        _, created = UserDomainRole.objects.get_or_create(
            user=lebowski_user, domain=self.domain_1, role=UserDomainRole.Roles.MANAGER
        )

        # Test for just 1 domain manager
        _, created = UserDomainRole.objects.get_or_create(
            user=meoward_user, domain=self.domain_2, role=UserDomainRole.Roles.MANAGER
        )

        with less_console_noise():
            self.domain_request_1 = completed_application(status=DomainApplication.ApplicationStatus.STARTED, name="city1.gov")
            self.domain_request_2 = completed_application(status=DomainApplication.ApplicationStatus.IN_REVIEW, name="city2.gov")
            self.domain_request_3 = completed_application(status=DomainApplication.ApplicationStatus.STARTED, name="city3.gov")
            self.domain_request_4 = completed_application(status=DomainApplication.ApplicationStatus.STARTED, name="city4.gov")
            self.domain_request_5 = completed_application(status=DomainApplication.ApplicationStatus.APPROVED, name="city5.gov")
            self.domain_request_3.submit()
            self.domain_request_3.save()
            self.domain_request_4.submit()
            self.domain_request_4.save()

    def tearDown(self):
        PublicContact.objects.all().delete()
        Domain.objects.all().delete()
        DomainInformation.objects.all().delete()
        DomainApplication.objects.all().delete()
        User.objects.all().delete()
        UserDomainRole.objects.all().delete()
        super().tearDown()