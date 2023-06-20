from django.test import TestCase, RequestFactory
from django.contrib.admin.sites import AdminSite
from registrar.admin import DomainApplicationAdmin
from registrar.models import DomainApplication, User
from .common import completed_application
from django.contrib.auth import get_user_model
from ..fsm_admin_mixins import FSMTransitionMixin

from django.conf import settings
from unittest.mock import MagicMock
import boto3_mocking  # type: ignore


class TestDomainApplicationAdmin(TestCase):
    def setUp(self):
        # Create a test instance of DomainApplication
        user = get_user_model().objects.create(username="username")
        self.model_instance = DomainApplication.objects.create(creator=user)
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

            # Create a mock request
            request = self.factory.post(
                "/admin/registrar/domainapplication/{}/change/".format(self.model_instance.pk)
            )
            
            user = get_user_model().objects.create(username="username2")
            request.user = user

            # Create an instance of the model admin
            model_admin = DomainApplicationAdmin(DomainApplication, self.site)

            # Modify the application's property
            self.model_instance.status = DomainApplication.INVESTIGATING

            # Use the model admin's save_model method
            super(FSMTransitionMixin, model_admin).save_model(request, self.model_instance, form=None, change=True)
            
            # Trigger the email:
            # Unfortunately, the email which triggers as a side effect of FSMTransitionMixin
            # does not trigger in this test. We need to manually trigger its send. 
            # application._send_in_review_email()

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
