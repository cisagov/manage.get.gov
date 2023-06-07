from django.test import TestCase, RequestFactory
from django.contrib.admin.sites import AdminSite
from registrar.admin import DomainApplicationAdmin
from django.contrib.auth import get_user_model
from registrar.models import Contact, DraftDomain, Website, DomainApplication, User

from django.conf import settings
from unittest.mock import MagicMock, ANY
import boto3_mocking  # type: ignore


class TestDomainApplicationAdmin(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()

    def _completed_application(
        self,
        has_other_contacts=True,
        has_current_website=True,
        has_alternative_gov_domain=True,
        has_type_of_work=True,
        has_anything_else=True,
    ):
        """A completed domain application."""
        user = get_user_model().objects.create(username="username")
        ao, _ = Contact.objects.get_or_create(
            first_name="Testy",
            last_name="Tester",
            title="Chief Tester",
            email="testy@town.com",
            phone="(555) 555 5555",
        )
        domain, _ = DraftDomain.objects.get_or_create(name="city.gov")
        alt, _ = Website.objects.get_or_create(website="city1.gov")
        current, _ = Website.objects.get_or_create(website="city.com")
        you, _ = Contact.objects.get_or_create(
            first_name="Testy you",
            last_name="Tester you",
            title="Admin Tester",
            email="mayor@igorville.gov",
            phone="(555) 555 5556",
        )
        other, _ = Contact.objects.get_or_create(
            first_name="Testy2",
            last_name="Tester2",
            title="Another Tester",
            email="testy2@town.com",
            phone="(555) 555 5557",
        )
        domain_application_kwargs = dict(
            organization_type="federal",
            federal_type="executive",
            purpose="Purpose of the site",
            is_policy_acknowledged=True,
            organization_name="Testorg",
            address_line1="address 1",
            address_line2="address 2",
            state_territory="NY",
            zipcode="10002",
            authorizing_official=ao,
            requested_domain=domain,
            submitter=you,
            creator=user,
        )
        if has_type_of_work:
            domain_application_kwargs["type_of_work"] = "e-Government"
        if has_anything_else:
            domain_application_kwargs["anything_else"] = "There is more"

        application, _ = DomainApplication.objects.get_or_create(
            **domain_application_kwargs
        )

        if has_other_contacts:
            application.other_contacts.add(other)
        if has_current_website:
            application.current_websites.add(current)
        if has_alternative_gov_domain:
            application.alternative_domains.add(alt)

        return application

    @boto3_mocking.patching
    def test_save_model_sends_email_on_property_change(self):
        # make sure there is no user with this email
        EMAIL = "mayor@igorville.gov"
        User.objects.filter(email=EMAIL).delete()

        mock_client = MagicMock()
        mock_client_instance = mock_client.return_value

        with boto3_mocking.clients.handler_for("sesv2", mock_client):
            # Create a sample application
            application = self._completed_application()

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
        email_body = email_content['Simple']['Body']['Text']['Data']

        # Assert or perform other checks on the email details
        expected_string = "Your .gov domain request is being reviewed"
        assert from_email == settings.DEFAULT_FROM_EMAIL
        assert to_email == EMAIL
        assert expected_string in email_body

        # Perform assertions on the mock call itself
        mock_client_instance.send_email.assert_called_once()

        # Cleanup
        application.delete()
