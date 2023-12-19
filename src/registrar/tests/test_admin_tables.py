from django.test import TestCase, RequestFactory, Client
from django.contrib.admin.sites import AdminSite

from registrar.admin import (
    DomainApplicationAdmin,
)
from registrar.models import (
    Domain,
    DomainApplication,
    DomainInformation,
    User,
    Contact,
    Website
)
from .common import (
    generic_domain_object,
    create_superuser,
    create_user,
    multiple_unalphabetical_domain_objects,
)

import logging

logger = logging.getLogger(__name__)


class TestDomainApplicationAdmin(TestCase):
    def setUp(self):
        super().setUp()
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.admin = DomainApplicationAdmin(model=DomainApplication, admin_site=self.site)
        self.superuser = create_superuser()
        self.staffuser = create_user()
        self.client = Client(HTTP_HOST="localhost:8080")

    def test_has_correct_filters(self):
        """Tests if DomainApplicationAdmin has the correct filters"""
        request = self.factory.get("/")
        request.user = self.superuser

        # Grab the current list of table filters
        readonly_fields = self.admin.get_list_filter(request)
        expected_fields = ("status", "organization_type", DomainApplicationAdmin.InvestigatorFilter)

        self.assertEqual(readonly_fields, expected_fields)

    def test_table_sorted_alphabetically(self):
        """Tests if DomainApplicationAdmin table is sorted alphabetically"""
        # Creates a list of DomainApplications in scrambled order
        multiple_unalphabetical_domain_objects("application")

        request = self.factory.get("/")
        request.user = self.superuser

        # Get the expected list of alphabetically sorted DomainApplications
        expected_order = DomainApplication.objects.order_by("requested_domain__name")

        # Get the returned queryset
        queryset = self.admin.get_queryset(request)

        # Check the order
        self.assertEqual(
            list(queryset),
            list(expected_order),
        )

    def test_displays_investigator_filter(self):
        """Tests if DomainApplicationAdmin displays the investigator filter"""

        # Create a mock DomainApplication object, with a fake investigator
        application: DomainApplication = generic_domain_object("application", "SomeGuy")
        investigator_user = User.objects.filter(username=application.investigator.username).get()
        investigator_user.is_staff = True
        investigator_user.save()

        p = "userpass"
        self.client.login(username="staffuser", password=p)
        response = self.client.get(
            "/admin/registrar/domainapplication/",
            {
                "investigator__id__exact": investigator_user.id,
            },
            follow=True,
        )

        # Then, test if the filter actually exists
        self.assertIn("filters", response.context)

        # Assert the content of filters and search_query
        filters = response.context["filters"]

        # Ensure that the format is correct. We will test the value later in the test.
        self.assertEqual(
            filters,
            [
                {
                    "parameter_name": "investigator",
                    "parameter_value": "SomeGuy first_name:investigator SomeGuy last_name:investigator",
                },
            ],
        )

    def test_investigator_filter_filters_correctly(self):
        """Tests the investigator filter"""

        # Create a mock DomainApplication object, with a fake investigator
        application: DomainApplication = generic_domain_object("application", "SomeGuy")
        investigator_user = User.objects.filter(username=application.investigator.username).get()
        investigator_user.is_staff = True
        investigator_user.save()

        # Create a second mock DomainApplication object, to test filtering
        application: DomainApplication = generic_domain_object("application", "BadGuy")
        another_user = User.objects.filter(username=application.investigator.username).get()
        another_user.is_staff = True
        another_user.save()

        p = "userpass"
        self.client.login(username="staffuser", password=p)
        response = self.client.get(
            "/admin/registrar/domainapplication/",
            {
                "investigator__id__exact": investigator_user.id,
            },
            follow=True,
        )

        expected_name = "SomeGuy first_name:investigator SomeGuy last_name:investigator"
        # We expect to see this four times, two of them are from the html for the filter,
        # the other two are the html from the list entry in the table.
        self.assertContains(response, expected_name, count=4)

        # Check that we don't also get the thing we aren't filtering for.
        # We expect to see this two times, two of them are from the html for the filter.
        unexpected_name = "BadGuy first_name:investigator BadGuy last_name:investigator"
        self.assertContains(response, unexpected_name, count=2)

    def tearDown(self):
        super().tearDown()
        Domain.objects.all().delete()
        DomainInformation.objects.all().delete()
        DomainApplication.objects.all().delete()
        User.objects.all().delete()
        Contact.objects.all().delete()
        Website.objects.all().delete()