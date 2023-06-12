from django.test import TestCase, RequestFactory
from django.contrib.admin.sites import AdminSite
from registrar.admin import DomainApplicationAdmin
from registrar.models import DomainApplication, User
from .common import completed_application

from django.conf import settings
from unittest.mock import MagicMock
import boto3_mocking  # type: ignore


class TestDomainApplicationAdmin(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()

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
            application.status = "investigating"

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
