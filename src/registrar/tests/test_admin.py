from django.test import TestCase, RequestFactory, Client
from django.contrib.admin.sites import AdminSite
from registrar.admin import DomainApplicationAdmin, ListHeaderAdmin, AuditedAdmin
from registrar.models import DomainApplication, User
from .common import completed_application

from django.conf import settings
from unittest.mock import MagicMock
import boto3_mocking  # type: ignore


class TestDomainApplicationAdmin(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.admin = ListHeaderAdmin(model=DomainApplication, admin_site=None)
        self.client = Client(HTTP_HOST='localhost:8080')

    @boto3_mocking.patching
    def test_save_model_sends_email_on_property_change(self):
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
            application.status = DomainApplication.INVESTIGATING

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
        expected_string = "Your .gov domain request is being reviewed"
        self.assertEqual(from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(to_email, EMAIL)
        self.assertIn(expected_string, email_body)

        # Perform assertions on the mock call itself
        mock_client_instance.send_email.assert_called_once()

        # Cleanup
        application.delete()
        
    def test_changelist_view(self):
        # Make the request using the Client class
        # which handles CSRF
        # Follow=True handles the redirect
        request = self.client.get('/admin/registrar/domainapplication/', {'param1': 'value1', 'param2': 'value2'}, follow=True, max_redirects=10)
        
        print(f'request {request}')
        
        # request = self.factory.get('/admin/registrar/domainapplication/')
        # # Set the GET parameters for testing
        # request.GET = {'param1': 'value1', 'param2': 'value2', 'q': 'search_value'}
        # # Call the changelist_view method
        response = self.admin.changelist_view(request, extra_context={'filters': [{'parameter_name': 'status', 'parameter_value': 'started'}], 'search_query': ''})
        
        
        print(f'response {response}')
        
        # Assert that the final response is a successful response (not a redirect)
        # self.assertEqual(response.status_code, 200)
        
        # Assert that the filters and search_query are added to the extra_context
        self.assertIn('filters', response.extra_context)
        self.assertIn('search_query', response.extra_context)
        # Assert the content of filters and search_query
        filters = response.extra_context['filters']
        search_query = response.extra_context['search_query']
        self.assertEqual(filters, [{'parameter_name': 'param1', 'parameter_value': 'value1'},
                                   {'parameter_name': 'param2', 'parameter_value': 'value2'}])
        self.assertEqual(search_query, 'value of q parameter if present in the request GET')
        
    def test_get_filters(self):
        # Create a mock request object
        request = self.factory.get('/admin/yourmodel/')
        # Set the GET parameters for testing
        request.GET = {'param1': 'value1', 'param2': 'value2', 'q': 'search_value'}
        # Call the get_filters method
        filters = self.admin.get_filters(request)
        
        # Assert the filters extracted from the request GET
        self.assertEqual(filters, [{'parameter_name': 'param1', 'parameter_value': 'value1'},
                                   {'parameter_name': 'param2', 'parameter_value': 'value2'}])
