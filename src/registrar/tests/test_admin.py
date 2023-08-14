from django.test import TestCase, RequestFactory, Client
from django.contrib.admin.sites import AdminSite
from registrar.admin import DomainApplicationAdmin, ListHeaderAdmin, MyUserAdmin, AuditedAdmin
from registrar.models import DomainApplication, DomainInformation, User
from registrar.models.contact import Contact
from .common import completed_application, mock_user, create_superuser, create_user, multiple_completed_applications_for_alphabetical_test
from django.contrib.auth import get_user_model

from django.conf import settings
from unittest.mock import MagicMock
import boto3_mocking  # type: ignore
import logging

logger = logging.getLogger(__name__)
class TestDomainApplicationAdmin(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()

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

            # Create an instance of the model admin
            model_admin = DomainApplicationAdmin(DomainApplication, self.site)

            # Modify the application's property
            application.status = DomainApplication.SUBMITTED

            # Use the model admin's save_model method
            model_admin.save_model(request, application, form=None, change=True)

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

            # Create an instance of the model admin
            model_admin = DomainApplicationAdmin(DomainApplication, self.site)

            # Modify the application's property
            application.status = DomainApplication.IN_REVIEW

            # Use the model admin's save_model method
            model_admin.save_model(request, application, form=None, change=True)

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

            # Create an instance of the model admin
            model_admin = DomainApplicationAdmin(DomainApplication, self.site)

            # Modify the application's property
            application.status = DomainApplication.APPROVED

            # Use the model admin's save_model method
            model_admin.save_model(request, application, form=None, change=True)

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

            # Create an instance of the model admin
            model_admin = DomainApplicationAdmin(DomainApplication, self.site)

            # Modify the application's property
            application.status = DomainApplication.ACTION_NEEDED

            # Use the model admin's save_model method
            model_admin.save_model(request, application, form=None, change=True)

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

            # Create an instance of the model admin
            model_admin = DomainApplicationAdmin(DomainApplication, self.site)

            # Modify the application's property
            application.status = DomainApplication.REJECTED

            # Use the model admin's save_model method
            model_admin.save_model(request, application, form=None, change=True)

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
        self.superuser.delete()


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

    def test_alphabetically_sorted_fk_fields_domain_application(self):
        tested_fields = [DomainApplication.authorizing_official.field, DomainApplication.submitter.field, DomainApplication.investigator.field, DomainApplication.creator.field]

        # Create a sample application - review status does not matter
        applications = multiple_completed_applications_for_alphabetical_test(status=DomainApplication.IN_REVIEW)

        # Create a mock request
        request = self.factory.post(
            "/admin/registrar/domainapplication/{}/change/".format(applications[0].pk)
        )
        
        model_admin = AuditedAdmin(DomainApplication, self.site)
        
        # Typically we wouldnt want two nested for fields, but both fields are of a fixed length.
        # For test case purposes, this should be performant.
        for field in tested_fields:
            first_name_field = "{}__first_name".format(field.name)
            last_name_field = "{}__last_name".format(field.name)

            desired_order = list(model_admin.get_queryset(request).order_by(first_name_field, last_name_field).values_list(first_name_field, last_name_field))
            current_sort_order: Contact = list(model_admin.formfield_for_foreignkey(field, request).queryset)

            current_sort_order_coerced_type = []

            # This is necessary as .queryset and get_queryset return lists of different types/structures.
            # We need to parse this data and coerce them into the same type.
            for contact in current_sort_order:
                first_name = contact.first_name
                last_name = contact.last_name

                match field.name:
                    case DomainApplication.authorizing_official.field.name:
                        name_tuple = self.coerced_fk_field_helper(first_name, last_name, 'ao', ':')
                        if name_tuple:
                            current_sort_order_coerced_type.append((first_name, last_name))
                    case DomainApplication.submitter.field.name:
                        name_tuple = self.coerced_fk_field_helper(first_name, last_name, 'you', ':')
                        if name_tuple:
                            current_sort_order_coerced_type.append((first_name, last_name))
                    case DomainApplication.investigator.field.name:
                        name_tuple = self.coerced_fk_field_helper(first_name, last_name, 'inv', ':')
                        if name_tuple:
                            current_sort_order_coerced_type.append((first_name, last_name))
                    case DomainApplication.creator.field.name:
                        name_tuple = self.coerced_fk_field_helper(first_name, last_name, 'cre', ':')
                        if name_tuple:
                            current_sort_order_coerced_type.append((first_name, last_name))

            self.assertEqual(desired_order, current_sort_order_coerced_type, "{} is not ordered alphabetically".format(field.name))

    # I originally spent some time trying to fully generalize this to replace the match/arg fields, 
    # but I think for this specific use-case its not necessary since it'll only be used here
    def coerced_fk_field_helper(self, first_name, last_name, field_name, queryset_shorthand):
        if(first_name and first_name.split(queryset_shorthand)[1] == field_name):
            return (first_name, last_name)
        else:
            return None
    
    def tearDown(self):
        DomainInformation.objects.all().delete()
        DomainApplication.objects.all().delete()
