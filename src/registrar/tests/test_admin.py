from django.test import TestCase, RequestFactory, Client
from django.contrib.admin.sites import AdminSite

from registrar.admin import (
    DomainAdmin,
    DomainApplicationAdmin,
    ListHeaderAdmin,
    MyUserAdmin,
    AuditedAdmin,
)
from registrar.models import (
    Domain,
    DomainApplication,
    DomainInformation,
    User,
    DomainInvitation,
)
from .common import (
    completed_application,
    mock_user,
    create_superuser,
    create_user,
    create_ready_domain,
    multiple_unalphabetical_domain_objects,
)

from django.contrib.auth import get_user_model
from unittest.mock import patch

from django.conf import settings
from unittest.mock import MagicMock
import boto3_mocking  # type: ignore
import logging

logger = logging.getLogger(__name__)


class TestDomainAdmin(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.admin = DomainAdmin(model=Domain, admin_site=self.site)
        self.client = Client(HTTP_HOST="localhost:8080")
        self.superuser = create_superuser()
        self.staffuser = create_user()

    def test_place_and_remove_hold(self):
        domain = create_ready_domain()

        # get admin page and assert Place Hold button
        p = "userpass"
        self.client.login(username="staffuser", password=p)
        response = self.client.get(
            "/admin/registrar/domain/{}/change/".format(domain.pk),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)
        self.assertContains(response, "Place hold")
        self.assertNotContains(response, "Remove hold")

        # submit place_client_hold and assert Remove Hold button
        response = self.client.post(
            "/admin/registrar/domain/{}/change/".format(domain.pk),
            {"_place_client_hold": "Place hold", "name": domain.name},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)
        self.assertContains(response, "Remove hold")
        self.assertNotContains(response, "Place hold")

        # submit remove client hold and assert Place hold button
        response = self.client.post(
            "/admin/registrar/domain/{}/change/".format(domain.pk),
            {"_remove_client_hold": "Remove hold", "name": domain.name},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, domain.name)
        self.assertContains(response, "Place hold")
        self.assertNotContains(response, "Remove hold")

    def tearDown(self):
        Domain.objects.all().delete()
        User.objects.all().delete()


class TestDomainApplicationAdmin(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.admin = DomainApplicationAdmin(
            model=DomainApplication, admin_site=self.site
        )
        self.superuser = create_superuser()
        self.staffuser = create_user()

    @boto3_mocking.patching
    def test_save_model_sends_submitted_email(self):
        # make sure there is no user with this email
        EMAIL = "mayor@igorville.gov"
        User.objects.filter(email=EMAIL).delete()

        mock_client = MagicMock()
        mock_client_instance = mock_client.return_value

        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            # Create a sample application
            application = completed_application()

            # Create a mock request
            request = self.factory.post(
                "/admin/registrar/domainapplication/{}/change/".format(application.pk)
            )

            # Modify the application's property
            application.status = DomainApplication.SUBMITTED

            # Use the model admin's save_model method
            self.admin.save_model(request, application, form=None, change=True)

        # Access the arguments passed to send_email
        call_args = mock_client_instance.send_email.call_args
        args, kwargs = call_args

        # Retrieve the email details from the arguments
        from_email = kwargs.get("FromEmailAddress")
        to_email = kwargs["Destination"]["ToAddresses"][0]
        email_content = kwargs["Content"]
        email_body = email_content["Simple"]["Body"]["Text"]["Data"]

        # Assert or perform other checks on the email details
        expected_string = "We received your .gov domain request."
        self.assertEqual(from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(to_email, EMAIL)
        self.assertIn(expected_string, email_body)

        # Perform assertions on the mock call itself
        mock_client_instance.send_email.assert_called_once()

    @boto3_mocking.patching
    def test_save_model_sends_in_review_email(self):
        # make sure there is no user with this email
        EMAIL = "mayor@igorville.gov"
        User.objects.filter(email=EMAIL).delete()

        mock_client = MagicMock()
        mock_client_instance = mock_client.return_value

        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            # Create a sample application
            application = completed_application(status=DomainApplication.SUBMITTED)

            # Create a mock request
            request = self.factory.post(
                "/admin/registrar/domainapplication/{}/change/".format(application.pk)
            )

            # Modify the application's property
            application.status = DomainApplication.IN_REVIEW

            # Use the model admin's save_model method
            self.admin.save_model(request, application, form=None, change=True)

        # Access the arguments passed to send_email
        call_args = mock_client_instance.send_email.call_args
        args, kwargs = call_args

        # Retrieve the email details from the arguments
        from_email = kwargs.get("FromEmailAddress")
        to_email = kwargs["Destination"]["ToAddresses"][0]
        email_content = kwargs["Content"]
        email_body = email_content["Simple"]["Body"]["Text"]["Data"]

        # Assert or perform other checks on the email details
        expected_string = "Your .gov domain request is being reviewed."
        self.assertEqual(from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(to_email, EMAIL)
        self.assertIn(expected_string, email_body)

        # Perform assertions on the mock call itself
        mock_client_instance.send_email.assert_called_once()

    @boto3_mocking.patching
    def test_save_model_sends_approved_email(self):
        # make sure there is no user with this email
        EMAIL = "mayor@igorville.gov"
        User.objects.filter(email=EMAIL).delete()

        mock_client = MagicMock()
        mock_client_instance = mock_client.return_value

        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            # Create a sample application
            application = completed_application(status=DomainApplication.IN_REVIEW)

            # Create a mock request
            request = self.factory.post(
                "/admin/registrar/domainapplication/{}/change/".format(application.pk)
            )

            # Modify the application's property
            application.status = DomainApplication.APPROVED

            # Use the model admin's save_model method
            self.admin.save_model(request, application, form=None, change=True)

        # Access the arguments passed to send_email
        call_args = mock_client_instance.send_email.call_args
        args, kwargs = call_args

        # Retrieve the email details from the arguments
        from_email = kwargs.get("FromEmailAddress")
        to_email = kwargs["Destination"]["ToAddresses"][0]
        email_content = kwargs["Content"]
        email_body = email_content["Simple"]["Body"]["Text"]["Data"]

        # Assert or perform other checks on the email details
        expected_string = "Congratulations! Your .gov domain request has been approved."
        self.assertEqual(from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(to_email, EMAIL)
        self.assertIn(expected_string, email_body)

        # Perform assertions on the mock call itself
        mock_client_instance.send_email.assert_called_once()

    def test_save_model_sets_approved_domain(self):
        # make sure there is no user with this email
        EMAIL = "mayor@igorville.gov"
        User.objects.filter(email=EMAIL).delete()

        # Create a sample application
        application = completed_application(status=DomainApplication.IN_REVIEW)

        # Create a mock request
        request = self.factory.post(
            "/admin/registrar/domainapplication/{}/change/".format(application.pk)
        )

        # Modify the application's property
        application.status = DomainApplication.APPROVED

        # Use the model admin's save_model method
        self.admin.save_model(request, application, form=None, change=True)

        # Test that approved domain exists and equals requested domain
        self.assertEqual(
            application.requested_domain.name, application.approved_domain.name
        )

    @boto3_mocking.patching
    def test_save_model_sends_action_needed_email(self):
        # make sure there is no user with this email
        EMAIL = "mayor@igorville.gov"
        User.objects.filter(email=EMAIL).delete()

        mock_client = MagicMock()
        mock_client_instance = mock_client.return_value

        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            # Create a sample application
            application = completed_application(status=DomainApplication.IN_REVIEW)

            # Create a mock request
            request = self.factory.post(
                "/admin/registrar/domainapplication/{}/change/".format(application.pk)
            )

            # Modify the application's property
            application.status = DomainApplication.ACTION_NEEDED

            # Use the model admin's save_model method
            self.admin.save_model(request, application, form=None, change=True)

        # Access the arguments passed to send_email
        call_args = mock_client_instance.send_email.call_args
        args, kwargs = call_args

        # Retrieve the email details from the arguments
        from_email = kwargs.get("FromEmailAddress")
        to_email = kwargs["Destination"]["ToAddresses"][0]
        email_content = kwargs["Content"]
        email_body = email_content["Simple"]["Body"]["Text"]["Data"]

        # Assert or perform other checks on the email details
        expected_string = (
            "We've identified an action needed to complete the "
            "review of your .gov domain request."
        )
        self.assertEqual(from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(to_email, EMAIL)
        self.assertIn(expected_string, email_body)

        # Perform assertions on the mock call itself
        mock_client_instance.send_email.assert_called_once()

    @boto3_mocking.patching
    def test_save_model_sends_rejected_email(self):
        # make sure there is no user with this email
        EMAIL = "mayor@igorville.gov"
        User.objects.filter(email=EMAIL).delete()

        mock_client = MagicMock()
        mock_client_instance = mock_client.return_value

        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            # Create a sample application
            application = completed_application(status=DomainApplication.IN_REVIEW)

            # Create a mock request
            request = self.factory.post(
                "/admin/registrar/domainapplication/{}/change/".format(application.pk)
            )

            # Modify the application's property
            application.status = DomainApplication.REJECTED

            # Use the model admin's save_model method
            self.admin.save_model(request, application, form=None, change=True)

        # Access the arguments passed to send_email
        call_args = mock_client_instance.send_email.call_args
        args, kwargs = call_args

        # Retrieve the email details from the arguments
        from_email = kwargs.get("FromEmailAddress")
        to_email = kwargs["Destination"]["ToAddresses"][0]
        email_content = kwargs["Content"]
        email_body = email_content["Simple"]["Body"]["Text"]["Data"]

        # Assert or perform other checks on the email details
        expected_string = "Your .gov domain request has been rejected."
        self.assertEqual(from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(to_email, EMAIL)
        self.assertIn(expected_string, email_body)

        # Perform assertions on the mock call itself
        mock_client_instance.send_email.assert_called_once()

    def test_save_model_sets_restricted_status_on_user(self):
        # make sure there is no user with this email
        EMAIL = "mayor@igorville.gov"
        User.objects.filter(email=EMAIL).delete()

        # Create a sample application
        application = completed_application(status=DomainApplication.IN_REVIEW)

        # Create a mock request
        request = self.factory.post(
            "/admin/registrar/domainapplication/{}/change/".format(application.pk)
        )

        # Modify the application's property
        application.status = DomainApplication.INELIGIBLE

        # Use the model admin's save_model method
        self.admin.save_model(request, application, form=None, change=True)

        # Test that approved domain exists and equals requested domain
        self.assertEqual(application.creator.status, "restricted")

    def test_readonly_when_restricted_creator(self):
        application = completed_application(status=DomainApplication.IN_REVIEW)
        application.creator.status = User.RESTRICTED
        application.creator.save()

        request = self.factory.get("/")
        request.user = self.superuser

        readonly_fields = self.admin.get_readonly_fields(request, application)

        expected_fields = [
            "id",
            "created_at",
            "updated_at",
            "status",
            "creator",
            "investigator",
            "organization_type",
            "federally_recognized_tribe",
            "state_recognized_tribe",
            "tribe_name",
            "federal_agency",
            "federal_type",
            "is_election_board",
            "organization_name",
            "address_line1",
            "address_line2",
            "city",
            "state_territory",
            "zipcode",
            "urbanization",
            "type_of_work",
            "more_organization_information",
            "authorizing_official",
            "approved_domain",
            "requested_domain",
            "submitter",
            "purpose",
            "no_other_contacts_rationale",
            "anything_else",
            "is_policy_acknowledged",
            "current_websites",
            "other_contacts",
            "alternative_domains",
        ]

        self.assertEqual(readonly_fields, expected_fields)

    def test_readonly_fields_for_analyst(self):
        request = self.factory.get("/")  # Use the correct method and path
        request.user = self.staffuser

        readonly_fields = self.admin.get_readonly_fields(request)

        expected_fields = [
            "creator",
            "type_of_work",
            "more_organization_information",
            "address_line1",
            "address_line2",
            "zipcode",
            "requested_domain",
            "alternative_domains",
            "purpose",
            "submitter",
            "no_other_contacts_rationale",
            "anything_else",
            "is_policy_acknowledged",
        ]

        self.assertEqual(readonly_fields, expected_fields)

    def test_readonly_fields_for_superuser(self):
        request = self.factory.get("/")  # Use the correct method and path
        request.user = self.superuser

        readonly_fields = self.admin.get_readonly_fields(request)

        expected_fields = []

        self.assertEqual(readonly_fields, expected_fields)

    def test_saving_when_restricted_creator(self):
        # Create an instance of the model
        application = completed_application(status=DomainApplication.IN_REVIEW)
        application.creator.status = User.RESTRICTED
        application.creator.save()

        # Create a request object with a superuser
        request = self.factory.get("/")
        request.user = self.superuser

        with patch("django.contrib.messages.error") as mock_error:
            # Simulate saving the model
            self.admin.save_model(request, application, None, False)

            # Assert that the error message was called with the correct argument
            mock_error.assert_called_once_with(
                request,
                "This action is not permitted for applications "
                + "with a restricted creator.",
            )

        # Assert that the status has not changed
        self.assertEqual(application.status, DomainApplication.IN_REVIEW)

    def test_change_view_with_restricted_creator(self):
        # Create an instance of the model
        application = completed_application(status=DomainApplication.IN_REVIEW)
        application.creator.status = User.RESTRICTED
        application.creator.save()

        with patch("django.contrib.messages.warning") as mock_warning:
            # Create a request object with a superuser
            request = self.factory.get(
                "/admin/your_app/domainapplication/{}/change/".format(application.pk)
            )
            request.user = self.superuser

            self.admin.display_restricted_warning(request, application)

            # Assert that the error message was called with the correct argument
            mock_warning.assert_called_once_with(
                request,
                "Cannot edit an application with a restricted creator.",
            )

    def tearDown(self):
        DomainInformation.objects.all().delete()
        DomainApplication.objects.all().delete()
        User.objects.all().delete()


class ListHeaderAdminTest(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.admin = ListHeaderAdmin(model=DomainApplication, admin_site=None)
        self.client = Client(HTTP_HOST="localhost:8080")
        self.superuser = create_superuser()

    def test_changelist_view(self):
        # Have to get creative to get past linter
        p = "adminpass"
        self.client.login(username="superuser", password=p)

        # Mock a user
        user = mock_user()

        # Make the request using the Client class
        # which handles CSRF
        # Follow=True handles the redirect
        response = self.client.get(
            "/admin/registrar/domainapplication/",
            {
                "status__exact": "started",
                "investigator__id__exact": user.id,
                "q": "Hello",
            },
            follow=True,
        )

        # Assert that the filters and search_query are added to the extra_context
        self.assertIn("filters", response.context)
        self.assertIn("search_query", response.context)
        # Assert the content of filters and search_query
        filters = response.context["filters"]
        search_query = response.context["search_query"]
        self.assertEqual(search_query, "Hello")
        self.assertEqual(
            filters,
            [
                {"parameter_name": "status", "parameter_value": "started"},
                {
                    "parameter_name": "investigator",
                    "parameter_value": user.first_name + " " + user.last_name,
                },
            ],
        )

    def test_get_filters(self):
        # Create a mock request object
        request = self.factory.get("/admin/yourmodel/")
        # Set the GET parameters for testing
        request.GET = {
            "status": "started",
            "investigator": "Rachid Mrad",
            "q": "search_value",
        }
        # Call the get_filters method
        filters = self.admin.get_filters(request)

        # Assert the filters extracted from the request GET
        self.assertEqual(
            filters,
            [
                {"parameter_name": "status", "parameter_value": "started"},
                {"parameter_name": "investigator", "parameter_value": "Rachid Mrad"},
            ],
        )

    def tearDown(self):
        # delete any applications too
        DomainInformation.objects.all().delete()
        DomainApplication.objects.all().delete()
        User.objects.all().delete()


class MyUserAdminTest(TestCase):
    def setUp(self):
        admin_site = AdminSite()
        self.admin = MyUserAdmin(model=get_user_model(), admin_site=admin_site)

    def test_list_display_without_username(self):
        request = self.client.request().wsgi_request
        request.user = create_user()

        list_display = self.admin.get_list_display(request)
        expected_list_display = (
            "email",
            "first_name",
            "last_name",
            "is_staff",
            "is_superuser",
        )

        self.assertEqual(list_display, expected_list_display)
        self.assertNotIn("username", list_display)

    def test_get_fieldsets_superuser(self):
        request = self.client.request().wsgi_request
        request.user = create_superuser()
        fieldsets = self.admin.get_fieldsets(request)
        expected_fieldsets = super(MyUserAdmin, self.admin).get_fieldsets(request)
        self.assertEqual(fieldsets, expected_fieldsets)

    def test_get_fieldsets_non_superuser(self):
        request = self.client.request().wsgi_request
        request.user = create_user()
        fieldsets = self.admin.get_fieldsets(request)
        expected_fieldsets = ((None, {"fields": []}),)
        self.assertEqual(fieldsets, expected_fieldsets)

    def tearDown(self):
        User.objects.all().delete()


class AuditedAdminTest(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.client = Client(HTTP_HOST="localhost:8080")

    def order_by_desired_field_helper(
        self, obj_to_sort: AuditedAdmin, request, field_name, *obj_names
    ):
        formatted_sort_fields = []
        for obj in obj_names:
            formatted_sort_fields.append("{}__{}".format(field_name, obj))

        ordered_list = list(
            obj_to_sort.get_queryset(request)
            .order_by(*formatted_sort_fields)
            .values_list(*formatted_sort_fields)
        )

        return ordered_list

    def test_alphabetically_sorted_fk_fields_domain_application(self):
        tested_fields = [
            DomainApplication.authorizing_official.field,
            DomainApplication.submitter.field,
            DomainApplication.investigator.field,
            DomainApplication.creator.field,
            DomainApplication.requested_domain.field,
        ]

        # Creates multiple domain applications - review status does not matter
        applications = multiple_unalphabetical_domain_objects("application")

        # Create a mock request
        request = self.factory.post(
            "/admin/registrar/domainapplication/{}/change/".format(applications[0].pk)
        )

        model_admin = AuditedAdmin(DomainApplication, self.site)

        sorted_fields = []
        # Typically we wouldn't want two nested for fields,
        # but both fields are of a fixed length.
        # For test case purposes, this should be performant.
        for field in tested_fields:
            isNamefield: bool = field == DomainApplication.requested_domain.field
            if isNamefield:
                sorted_fields = ["name"]
            else:
                sorted_fields = ["first_name", "last_name"]
            # We want both of these to be lists, as it is richer test wise.

            desired_order = self.order_by_desired_field_helper(
                model_admin, request, field.name, *sorted_fields
            )
            current_sort_order = list(
                model_admin.formfield_for_foreignkey(field, request).queryset
            )

            # Conforms to the same object structure as desired_order
            current_sort_order_coerced_type = []

            # This is necessary as .queryset and get_queryset
            # return lists of different types/structures.
            # We need to parse this data and coerce them into the same type.
            for contact in current_sort_order:
                if not isNamefield:
                    first = contact.first_name
                    last = contact.last_name
                else:
                    first = contact.name
                    last = None

                name_tuple = self.coerced_fk_field_helper(first, last, field.name, ":")
                if name_tuple is not None:
                    current_sort_order_coerced_type.append(name_tuple)

            self.assertEqual(
                desired_order,
                current_sort_order_coerced_type,
                "{} is not ordered alphabetically".format(field.name),
            )

    def test_alphabetically_sorted_fk_fields_domain_information(self):
        tested_fields = [
            DomainInformation.authorizing_official.field,
            DomainInformation.submitter.field,
            DomainInformation.creator.field,
            (DomainInformation.domain.field, ["name"]),
            (DomainInformation.domain_application.field, ["requested_domain__name"]),
        ]
        # Creates multiple domain applications - review status does not matter
        applications = multiple_unalphabetical_domain_objects("information")

        # Create a mock request
        request = self.factory.post(
            "/admin/registrar/domaininformation/{}/change/".format(applications[0].pk)
        )

        model_admin = AuditedAdmin(DomainInformation, self.site)

        sorted_fields = []
        # Typically we wouldn't want two nested for fields,
        # but both fields are of a fixed length.
        # For test case purposes, this should be performant.
        for field in tested_fields:
            isOtherOrderfield: bool = isinstance(field, tuple)
            field_obj = None
            if isOtherOrderfield:
                sorted_fields = field[1]
                field_obj = field[0]
            else:
                sorted_fields = ["first_name", "last_name"]
                field_obj = field
            # We want both of these to be lists, as it is richer test wise.
            desired_order = self.order_by_desired_field_helper(
                model_admin, request, field_obj.name, *sorted_fields
            )
            current_sort_order = list(
                model_admin.formfield_for_foreignkey(field_obj, request).queryset
            )

            # Conforms to the same object structure as desired_order
            current_sort_order_coerced_type = []

            # This is necessary as .queryset and get_queryset
            # return lists of different types/structures.
            # We need to parse this data and coerce them into the same type.
            for obj in current_sort_order:
                last = None
                if not isOtherOrderfield:
                    first = obj.first_name
                    last = obj.last_name
                elif field_obj == DomainInformation.domain.field:
                    first = obj.name
                elif field_obj == DomainInformation.domain_application.field:
                    first = obj.requested_domain.name

                name_tuple = self.coerced_fk_field_helper(
                    first, last, field_obj.name, ":"
                )
                if name_tuple is not None:
                    current_sort_order_coerced_type.append(name_tuple)

            self.assertEqual(
                desired_order,
                current_sort_order_coerced_type,
                "{} is not ordered alphabetically".format(field_obj.name),
            )

    def test_alphabetically_sorted_fk_fields_domain_invitation(self):
        tested_fields = [DomainInvitation.domain.field]

        # Creates multiple domain applications - review status does not matter
        applications = multiple_unalphabetical_domain_objects("invitation")

        # Create a mock request
        request = self.factory.post(
            "/admin/registrar/domaininvitation/{}/change/".format(applications[0].pk)
        )

        model_admin = AuditedAdmin(DomainInvitation, self.site)

        sorted_fields = []
        # Typically we wouldn't want two nested for fields,
        # but both fields are of a fixed length.
        # For test case purposes, this should be performant.
        for field in tested_fields:
            sorted_fields = ["name"]
            # We want both of these to be lists, as it is richer test wise.

            desired_order = self.order_by_desired_field_helper(
                model_admin, request, field.name, *sorted_fields
            )
            current_sort_order = list(
                model_admin.formfield_for_foreignkey(field, request).queryset
            )

            # Conforms to the same object structure as desired_order
            current_sort_order_coerced_type = []

            # This is necessary as .queryset and get_queryset
            # return lists of different types/structures.
            # We need to parse this data and coerce them into the same type.
            for contact in current_sort_order:
                first = contact.name
                last = None

                name_tuple = self.coerced_fk_field_helper(first, last, field.name, ":")
                if name_tuple is not None:
                    current_sort_order_coerced_type.append(name_tuple)

            self.assertEqual(
                desired_order,
                current_sort_order_coerced_type,
                "{} is not ordered alphabetically".format(field.name),
            )

    def coerced_fk_field_helper(
        self, first_name, last_name, field_name, queryset_shorthand
    ):
        """Handles edge cases for test cases"""
        if first_name is None:
            raise ValueError("Invalid value for first_name, must be defined")

        returned_tuple = (first_name, last_name)
        # Handles edge case for names - structured strangely
        if last_name is None:
            return (first_name,)

        if first_name.split(queryset_shorthand)[1] == field_name:
            return returned_tuple
        else:
            return None

    def tearDown(self):
        DomainInformation.objects.all().delete()
        DomainApplication.objects.all().delete()
        DomainInvitation.objects.all().delete()
