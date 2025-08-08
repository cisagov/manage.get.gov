"""Test form validation requirements."""

import json
from django.test import TestCase, RequestFactory
from api.views import available
from api.tests.common import less_console_noise_decorator

from registrar.forms.domain_request_wizard import (
    AlternativeDomainForm,
    CurrentSitesForm,
    DotGovDomainForm,
    SeniorOfficialForm,
    OrganizationContactForm,
    OtherContactsForm,
    RequirementsForm,
    TribalGovernmentForm,
    AnythingElseForm,
    AboutYourOrganizationForm,
)
from registrar.forms import PurposeDetailsForm

from registrar.forms.domain import ContactForm
from registrar.forms.portfolio import (
    PortfolioInvitedMemberForm,
    PortfolioMemberForm,
    PortfolioNewMemberForm,
)
from registrar.models.portfolio import Portfolio
from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.user import User
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices
from registrar.tests.common import MockEppLib, create_user
from django.contrib.auth import get_user_model


class TestFormValidation(MockEppLib):
    def setUp(self):
        super().setUp()
        self.API_BASE_PATH = "/api/v1/available/?domain="
        self.user = get_user_model().objects.create(username="username")
        self.factory = RequestFactory()

    @less_console_noise_decorator
    def test_org_contact_zip_invalid(self):
        form = OrganizationContactForm(data={"zipcode": "nah"})
        self.assertEqual(
            form.errors["zipcode"],
            ["Enter a 5-digit or 9-digit zip code, like 12345 or 12345-6789."],
        )

    @less_console_noise_decorator
    def test_org_contact_zip_valid(self):
        for zipcode in ["12345", "12345-6789"]:
            form = OrganizationContactForm(data={"zipcode": zipcode})
            self.assertNotIn("zipcode", form.errors)

    @less_console_noise_decorator
    def test_website_invalid(self):
        form = CurrentSitesForm(data={"website": "nah"})
        self.assertEqual(
            form.errors["website"],
            ["Enter your organization's current website in the required format, like example.com."],
        )

    @less_console_noise_decorator
    def test_website_valid(self):
        form = CurrentSitesForm(data={"website": "hyphens-rule.gov.uk"})
        self.assertEqual(len(form.errors), 0)

    @less_console_noise_decorator
    def test_website_scheme_valid(self):
        form = CurrentSitesForm(data={"website": "http://hyphens-rule.gov.uk"})
        self.assertEqual(len(form.errors), 0)
        form = CurrentSitesForm(data={"website": "https://hyphens-rule.gov.uk"})
        self.assertEqual(len(form.errors), 0)

    @less_console_noise_decorator
    def test_requested_domain_valid(self):
        """Just a valid domain name with no .gov at the end."""
        form = DotGovDomainForm(data={"requested_domain": "top-level-agency"})
        self.assertEqual(len(form.errors), 0)

    @less_console_noise_decorator
    def test_requested_domain_starting_www(self):
        """Test a valid domain name with .www at the beginning."""
        form = DotGovDomainForm(data={"requested_domain": "www.top-level-agency"})
        self.assertEqual(len(form.errors), 0)
        self.assertEqual(form.cleaned_data["requested_domain"], "top-level-agency")

    @less_console_noise_decorator
    def test_requested_domain_ending_dotgov(self):
        """Just a valid domain name with .gov at the end."""
        form = DotGovDomainForm(data={"requested_domain": "top-level-agency.gov"})
        self.assertEqual(len(form.errors), 0)
        self.assertEqual(form.cleaned_data["requested_domain"], "top-level-agency")

    @less_console_noise_decorator
    def test_requested_domain_ending_dotcom_invalid(self):
        """don't accept domains ending other than .gov."""
        form = DotGovDomainForm(data={"requested_domain": "top-level-agency.com"})
        self.assertEqual(
            form.errors["requested_domain"],
            ["Enter the .gov domain you want without any periods."],
        )

    @less_console_noise_decorator
    def test_requested_domain_errors_consistent(self):
        """Tests if the errors on submit and with the check availability buttons are consistent
        for requested_domains
        """
        test_cases = [
            # extra_dots
            ("top-level-agency.com", "Enter the .gov domain you want without any periods."),
            # invalid
            (
                "underscores_forever",
                "Enter a domain using only letters, numbers, " "or hyphens (though we don't recommend using hyphens).",
            ),
            # required
            (
                "",
                "Enter the .gov domain you want. Don’t include “www” or “.gov.”"
                " For example, if you want www.city.gov, you would enter “city”"
                " (without the quotes).",
            ),
            # unavailable
            (
                "whitehouse.gov",
                "That domain isn’t available. <a class='usa-link' "
                "href='https://get.gov/domains/choosing' target='_blank'>Read more about "
                "choosing your .gov domain</a>.",
            ),
        ]

        for domain, expected_error in test_cases:
            with self.subTest(domain=domain, error=expected_error):
                form = DotGovDomainForm(data={"requested_domain": domain})

                form_error = list(form.errors["requested_domain"])

                # Ensure the form returns what we expect
                self.assertEqual(
                    form_error,
                    [expected_error],
                )

                request = self.factory.get(self.API_BASE_PATH + domain)
                request.user = self.user
                response = available(request, domain=domain)

                # Ensure that we're getting the right kind of response
                self.assertContains(response, "available")

                response_object = json.loads(response.content)

                json_error = response_object["message"]
                # Test if the message is what we expect
                self.assertEqual(json_error, expected_error)

                # While its implied,
                # for good measure, test if the two objects are equal anyway
                self.assertEqual([json_error], form_error)

    @less_console_noise_decorator
    def test_alternate_domain_errors_consistent(self):
        """Tests if the errors on submit and with the check availability buttons are consistent
        for alternative_domains
        """
        test_cases = [
            # extra_dots
            ("top-level-agency.com", "Enter the .gov domain you want without any periods."),
            # invalid
            (
                "underscores_forever",
                "Enter a domain using only letters, numbers, " "or hyphens (though we don't recommend using hyphens).",
            ),
            # unavailable
            (
                "whitehouse.gov",
                "That domain isn’t available. <a class='usa-link' "
                "href='https://get.gov/domains/choosing' target='_blank'>Read more about "
                "choosing your .gov domain</a>.",
            ),
        ]

        for domain, expected_error in test_cases:
            with self.subTest(domain=domain, error=expected_error):
                form = AlternativeDomainForm(data={"alternative_domain": domain})

                form_error = list(form.errors["alternative_domain"])

                # Ensure the form returns what we expect
                self.assertEqual(
                    form_error,
                    [expected_error],
                )

                request = self.factory.get(self.API_BASE_PATH + domain)
                request.user = self.user
                response = available(request, domain=domain)

                # Ensure that we're getting the right kind of response
                self.assertContains(response, "available")

                response_object = json.loads(response.content)

                json_error = response_object["message"]
                # Test if the message is what we expect
                self.assertEqual(json_error, expected_error)

                # While its implied,
                # for good measure, test if the two objects are equal anyway
                self.assertEqual([json_error], form_error)

    @less_console_noise_decorator
    def test_requested_domain_two_dots_invalid(self):
        """don't accept domains that are subdomains"""
        form = DotGovDomainForm(data={"requested_domain": "sub.top-level-agency.gov"})
        self.assertEqual(
            form.errors["requested_domain"],
            ["Enter the .gov domain you want without any periods."],
        )
        form = DotGovDomainForm(data={"requested_domain": ".top-level-agency.gov"})
        self.assertEqual(
            form.errors["requested_domain"],
            ["Enter the .gov domain you want without any periods."],
        )
        form = DotGovDomainForm(data={"requested_domain": "..gov"})
        self.assertEqual(
            form.errors["requested_domain"],
            ["Enter the .gov domain you want without any periods."],
        )

    @less_console_noise_decorator
    def test_requested_domain_invalid_characters(self):
        """must be a valid .gov domain name."""
        form = DotGovDomainForm(data={"requested_domain": "underscores_forever"})
        self.assertEqual(
            form.errors["requested_domain"],
            ["Enter a domain using only letters, numbers, or hyphens (though we don't recommend using hyphens)."],
        )

    @less_console_noise_decorator
    def test_senior_official_email_invalid(self):
        """must be a valid email address."""
        form = SeniorOfficialForm(data={"email": "boss@boss"})
        self.assertEqual(
            form.errors["email"],
            ["Enter an email address in the required format, like name@example.com."],
        )

    @less_console_noise_decorator
    def test_purpose_form_character_count_invalid(self):
        """Response must be less than 2000 characters."""
        form = PurposeDetailsForm(
            data={
                "purpose": "Bacon ipsum dolor amet fatback strip steak pastrami"
                "shankle, drumstick doner chicken landjaeger turkey andouille."
                "Buffalo biltong chuck pork chop tongue bresaola turkey. Doner"
                "ground round strip steak, jowl tail chuck ribeye bacon"
                "beef ribs swine filet ball tip pancetta strip steak sirloin"
                "mignon ham spare ribs rump. Tail shank biltong beef ribs doner"
                "buffalo swine bacon. Tongue cow picanha brisket bacon chuck"
                "leberkas pork loin pork, drumstick capicola. Doner short loin"
                "ground round fatback turducken chislic shoulder turducken"
                "spare ribs, burgdoggen kielbasa kevin frankfurter ball tip"
                "pancetta cupim. Turkey meatball andouille porchetta hamburger"
                "pork chop corned beef. Brisket short ribs turducken, pork chop"
                "chislic turkey ball pork chop leberkas rump, rump bacon, jowl"
                "tip ham. Shankle salami tongue venison short ribs kielbasa"
                "tri-tip ham hock swine hamburger. Flank meatball corned beef"
                "cow sausage ball tip kielbasa ham hock. Ball tip cupim meatloaf"
                "beef ribs rump jowl tenderloin swine sausage biltong"
                "bacon rump tail boudin meatball boudin meatball boudin."
                "Bacon ipsum dolor amet fatback strip steak pastrami"
                "shankle, drumstick doner chicken landjaeger turkey andouille."
                "Buffalo biltong chuck pork chop tongue bresaola turkey. Doner"
                "ground round strip steak, jowl tail chuck ribeye bacon"
                "beef ribs swine filet ball tip pancetta strip steak sirloin"
                "mignon ham spare ribs rump. Tail shank biltong beef ribs doner"
                "buffalo swine bacon. Tongue cow picanha brisket bacon chuck"
                "leberkas pork loin pork, drumstick capicola. Doner short loin"
                "ground round fatback turducken chislic shoulder turducken"
                "spare ribs, burgdoggen kielbasa kevin frankfurter ball tip"
                "pancetta cupim. Turkey meatball andouille porchetta hamburger"
                "pork chop corned beef. Brisket short ribs turducken, pork chop"
                "chislic turkey ball pork chop leberkas rump, rump bacon, jowl"
                "tip ham. Shankle salami tongue venison short ribs kielbasa"
                "tri-tip ham hock swine hamburger. Flank meatball corned beef"
                "cow sausage ball tip kielbasa ham hock. Ball tip cupim meatloaf"
                "beef ribs rump jowl tenderloin swine sausage biltong"
                "bacon rump tail boudin meatball boudin meatball boudin."
            }
        )
        self.assertEqual(
            form.errors["purpose"],
            ["Response must be less than 2000 characters."],
        )

    @less_console_noise_decorator
    def test_anything_else_form_about_your_organization_character_count_invalid(self):
        """Response must be less than 2000 characters."""
        form = AnythingElseForm(
            data={
                "anything_else": "Bacon ipsum dolor amet fatback strip steak pastrami"
                "shankle, drumstick doner chicken landjaeger turkey andouille."
                "Buffalo biltong chuck pork chop tongue bresaola turkey. Doner"
                "ground round strip steak, jowl tail chuck ribeye bacon"
                "beef ribs swine filet ball tip pancetta strip steak sirloin"
                "mignon ham spare ribs rump. Tail shank biltong beef ribs doner"
                "buffalo swine bacon. Tongue cow picanha brisket bacon chuck"
                "leberkas pork loin pork, drumstick capicola. Doner short loin"
                "ground round fatback turducken chislic shoulder turducken"
                "spare ribs, burgdoggen kielbasa kevin frankfurter ball tip"
                "pancetta cupim. Turkey meatball andouille porchetta hamburger"
                "pork chop corned beef. Brisket short ribs turducken, pork chop"
                "chislic turkey ball pork chop leberkas rump, rump bacon, jowl"
                "tip ham. Shankle salami tongue venison short ribs kielbasa"
                "tri-tip ham hock swine hamburger. Flank meatball corned beef"
                "cow sausage ball tip kielbasa ham hock. Ball tip cupim meatloaf"
                "beef ribs rump jowl tenderloin swine sausage biltong"
                "bacon rump tail boudin meatball boudin meatball boudin."
                "shankle, drumstick doner chicken landjaeger turkey andouille."
                "Buffalo biltong chuck pork chop tongue bresaola turkey. Doner"
                "ground round strip steak, jowl tail chuck ribeye bacon"
                "beef ribs swine filet ball tip pancetta strip steak sirloin"
                "mignon ham spare ribs rump. Tail shank biltong beef ribs doner"
                "buffalo swine bacon. Tongue cow picanha brisket bacon chuck"
                "leberkas pork loin pork, drumstick capicola. Doner short loin"
                "ground round fatback turducken chislic shoulder turducken"
                "spare ribs, burgdoggen kielbasa kevin frankfurter ball tip"
                "pancetta cupim. Turkey meatball andouille porchetta hamburger"
                "pork chop corned beef. Brisket short ribs turducken, pork chop"
                "chislic turkey ball pork chop leberkas rump, rump bacon, jowl"
                "tip ham. Shankle salami tongue venison short ribs kielbasa"
                "tri-tip ham hock swine hamburger. Flank meatball corned beef"
                "cow sausage ball tip kielbasa ham hock. Ball tip cupim meatloaf"
                "beef ribs rump jowl tenderloin swine sausage biltong"
                "bacon rump tail boudin meatball boudin meatball boudin."
            }
        )
        self.assertEqual(
            form.errors["anything_else"],
            ["Response must be less than 2000 characters."],
        )

    @less_console_noise_decorator
    def test_anything_else_form_character_count_invalid(self):
        """Response must be less than 2000 characters."""
        form = AboutYourOrganizationForm(
            data={
                "about_your_organization": "Bacon ipsum dolor amet fatback"
                "strip steak pastrami"
                "shankle, drumstick doner chicken landjaeger turkey andouille."
                "Buffalo biltong chuck pork chop tongue bresaola turkey. Doner"
                "ground round strip steak, jowl tail chuck ribeye bacon"
                "beef ribs swine filet ball tip pancetta strip steak sirloin"
                "mignon ham spare ribs rump. Tail shank biltong beef ribs doner"
                "buffalo swine bacon. Tongue cow picanha brisket bacon chuck"
                "leberkas pork loin pork, drumstick capicola. Doner short loin"
                "ground round fatback turducken chislic shoulder turducken"
                "spare ribs, burgdoggen kielbasa kevin frankfurter ball tip"
                "pancetta cupim. Turkey meatball andouille porchetta hamburger"
                "pork chop corned beef. Brisket short ribs turducken, pork chop"
                "chislic turkey ball pork chop leberkas rump, rump bacon, jowl"
                "tip ham. Shankle salami tongue venison short ribs kielbasa"
                "tri-tip ham hock swine hamburger. Flank meatball corned beef"
                "cow sausage ball tip kielbasa ham hock. Ball tip cupim meatloaf"
                "beef ribs rump jowl tenderloin swine sausage biltong"
                "bacon rump tail boudin meatball boudin meatball boudin."
                "strip steak pastrami"
                "shankle, drumstick doner chicken landjaeger turkey andouille."
                "Buffalo biltong chuck pork chop tongue bresaola turkey. Doner"
                "ground round strip steak, jowl tail chuck ribeye bacon"
                "beef ribs swine filet ball tip pancetta strip steak sirloin"
                "mignon ham spare ribs rump. Tail shank biltong beef ribs doner"
                "buffalo swine bacon. Tongue cow picanha brisket bacon chuck"
                "leberkas pork loin pork, drumstick capicola. Doner short loin"
                "ground round fatback turducken chislic shoulder turducken"
                "spare ribs, burgdoggen kielbasa kevin frankfurter ball tip"
                "pancetta cupim. Turkey meatball andouille porchetta hamburger"
                "pork chop corned beef. Brisket short ribs turducken, pork chop"
                "chislic turkey ball pork chop leberkas rump, rump bacon, jowl"
                "tip ham. Shankle salami tongue venison short ribs kielbasa"
                "tri-tip ham hock swine hamburger. Flank meatball corned beef"
                "cow sausage ball tip kielbasa ham hock. Ball tip cupim meatloaf"
                "beef ribs rump jowl tenderloin swine sausage biltong"
                "bacon rump tail boudin meatball boudin meatball boudin."
            }
        )
        self.assertEqual(
            form.errors["about_your_organization"],
            ["Response must be less than 2000 characters."],
        )

    @less_console_noise_decorator
    def test_other_contact_email_invalid(self):
        """must be a valid email address."""
        form = OtherContactsForm(data={"email": "splendid@boss"})
        self.assertEqual(
            form.errors["email"],
            ["Enter an email address in the required format, like name@example.com."],
        )

    @less_console_noise_decorator
    def test_other_contact_phone_invalid(self):
        """Must be a valid phone number."""
        form = OtherContactsForm(data={"phone": "super@boss"})
        self.assertTrue(form.errors["phone"][0].startswith("Enter a valid 10-digit phone number."))

    @less_console_noise_decorator
    def test_requirements_form_blank(self):
        """Requirements box unchecked is an error."""
        form = RequirementsForm(data={})
        self.assertEqual(
            form.errors["is_policy_acknowledged"],
            ["Check the box if you read and agree to the requirements for operating a .gov domain."],
        )

    @less_console_noise_decorator
    def test_requirements_form_unchecked(self):
        """Requirements box unchecked is an error."""
        form = RequirementsForm(data={"is_policy_acknowledged": False})
        self.assertEqual(
            form.errors["is_policy_acknowledged"],
            ["Check the box if you read and agree to the requirements for operating a .gov domain."],
        )

    @less_console_noise_decorator
    def test_tribal_government_unrecognized(self):
        """Not state or federally recognized is an error."""
        form = TribalGovernmentForm(data={"state_recognized": False, "federally_recognized": False})
        self.assertTrue(any("tell us more about your tribe" in error for error in form.non_field_errors()))


class TestContactForm(TestCase):
    @less_console_noise_decorator
    def test_contact_form_email_invalid(self):
        form = ContactForm(data={"email": "example.net"})
        self.assertEqual(form.errors["email"], ["Enter a valid email address."])

    @less_console_noise_decorator
    def test_contact_form_email_invalid2(self):
        form = ContactForm(data={"email": "@"})
        self.assertEqual(form.errors["email"], ["Enter a valid email address."])


class TestBasePortfolioMemberForms(TestCase):
    """We test on the child forms instead of BasePortfolioMemberForm because the base form
    is a model form with no model bound."""

    def setUp(self):
        super().setUp()
        self.user = create_user()
        self.portfolio, _ = Portfolio.objects.get_or_create(
            creator_id=self.user.id, organization_name="Hotel California"
        )

    def tearDown(self):
        super().tearDown()
        Portfolio.objects.all().delete()
        UserPortfolioPermission.objects.all().delete()
        PortfolioInvitation.objects.all().delete()
        User.objects.all().delete()

    def _assert_form_is_valid(self, form_class, data, instance=None):
        if instance is not None:
            form = form_class(data=data, instance=instance)
        else:
            form = form_class(data=data)
        self.assertTrue(form.is_valid(), f"Form {form_class.__name__} failed validation with data: {data}")
        return form

    def _assert_form_has_error(self, form_class, data, field_name, instance=None):
        form = form_class(data=data, instance=instance)
        self.assertFalse(form.is_valid())
        self.assertIn(field_name, form.errors)

    def _assert_initial_data(self, form_class, instance, expected_initial_data):
        """Helper to check if the instance data is correctly mapped to the initial form values."""
        form = form_class(instance=instance)
        for field, expected_value in expected_initial_data.items():
            self.assertEqual(form.initial[field], expected_value)

    def _assert_permission_mapping(self, form_class, data, expected_permissions):
        """Helper to check if permissions are correctly handled and mapped."""
        form = self._assert_form_is_valid(form_class, data)
        cleaned_data = form.cleaned_data
        for permission in expected_permissions:
            self.assertIn(permission, cleaned_data["additional_permissions"])

    @less_console_noise_decorator
    def test_required_field_for_member(self):
        """Test that required fields are validated for a member role."""
        data = {
            "role": UserPortfolioRoleChoices.ORGANIZATION_MEMBER.value,
            "domain_request_permissions": "",  # Simulate missing field
            "domain_permissions": "",  # Simulate missing field
            "member_permissions": "",  # Simulate missing field
        }
        user_portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
            portfolio=self.portfolio, user=self.user
        )
        portfolio_invitation, _ = PortfolioInvitation.objects.get_or_create(portfolio=self.portfolio, email="hi@ho")

        # Check required fields for all forms
        self._assert_form_has_error(PortfolioMemberForm, data, "domain_request_permissions", user_portfolio_permission)
        self._assert_form_has_error(PortfolioMemberForm, data, "domain_permissions", user_portfolio_permission)
        self._assert_form_has_error(PortfolioMemberForm, data, "member_permissions", user_portfolio_permission)
        self._assert_form_has_error(
            PortfolioInvitedMemberForm, data, "domain_request_permissions", portfolio_invitation
        )
        self._assert_form_has_error(PortfolioInvitedMemberForm, data, "domain_permissions", portfolio_invitation)
        self._assert_form_has_error(PortfolioInvitedMemberForm, data, "member_permissions", portfolio_invitation)
        self._assert_form_has_error(PortfolioNewMemberForm, data, "domain_request_permissions", portfolio_invitation)
        self._assert_form_has_error(PortfolioNewMemberForm, data, "domain_permissions", portfolio_invitation)
        self._assert_form_has_error(PortfolioNewMemberForm, data, "member_permissions", portfolio_invitation)

    @less_console_noise_decorator
    def test_clean_validates_required_fields_for_admin_role(self):
        """Test that the `clean` method validates the correct fields for admin role.

        For PortfolioMemberForm and PortfolioInvitedMemberForm, we pass an object as the instance to the form.
        For UserPortfolioPermissionChoices, we add a portfolio and an email to the POST data.

        These things are handled in the views."""

        user_portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
            portfolio=self.portfolio, user=self.user
        )
        portfolio_invitation, _ = PortfolioInvitation.objects.get_or_create(portfolio=self.portfolio, email="hi@ho")
        data = {
            "role": UserPortfolioRoleChoices.ORGANIZATION_ADMIN.value,
        }

        # Check form validity for all forms
        form = self._assert_form_is_valid(PortfolioMemberForm, data, user_portfolio_permission)
        cleaned_data = form.cleaned_data
        self.assertEqual(cleaned_data["roles"], [UserPortfolioRoleChoices.ORGANIZATION_ADMIN.value])

        form = self._assert_form_is_valid(PortfolioInvitedMemberForm, data, portfolio_invitation)
        cleaned_data = form.cleaned_data
        self.assertEqual(cleaned_data["roles"], [UserPortfolioRoleChoices.ORGANIZATION_ADMIN.value])

        data = {
            "email": "hi@ho.com",
            "portfolio": self.portfolio.id,
            "role": UserPortfolioRoleChoices.ORGANIZATION_ADMIN.value,
        }

        form = self._assert_form_is_valid(PortfolioNewMemberForm, data)
        cleaned_data = form.cleaned_data
        self.assertEqual(cleaned_data["roles"], [UserPortfolioRoleChoices.ORGANIZATION_ADMIN.value])

    @less_console_noise_decorator
    def test_clean_validates_required_fields_for_basic_role(self):
        """Test that the `clean` method validates the correct fields for basic role.

        For PortfolioMemberForm and PortfolioInvitedMemberForm, we pass an object as the instance to the form.
        For UserPortfolioPermissionChoices, we add a portfolio and an email to the POST data.

        These things are handled in the views."""

        user_portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
            portfolio=self.portfolio, user=self.user
        )
        portfolio_invitation, _ = PortfolioInvitation.objects.get_or_create(portfolio=self.portfolio, email="hi@ho")

        data = {
            "role": UserPortfolioRoleChoices.ORGANIZATION_MEMBER.value,
            "domain_request_permissions": UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS.value,
            "domain_permissions": UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS.value,
            "member_permissions": UserPortfolioPermissionChoices.VIEW_MEMBERS.value,
        }

        # Check form validity for all forms
        form = self._assert_form_is_valid(PortfolioMemberForm, data, user_portfolio_permission)
        cleaned_data = form.cleaned_data
        self.assertEqual(cleaned_data["roles"], [UserPortfolioRoleChoices.ORGANIZATION_MEMBER.value])
        self.assertEqual(
            cleaned_data["domain_request_permissions"], UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS.value
        )
        self.assertEqual(cleaned_data["domain_permissions"], UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS.value)
        self.assertEqual(cleaned_data["member_permissions"], UserPortfolioPermissionChoices.VIEW_MEMBERS.value)

        form = self._assert_form_is_valid(PortfolioInvitedMemberForm, data, portfolio_invitation)
        cleaned_data = form.cleaned_data
        self.assertEqual(cleaned_data["roles"], [UserPortfolioRoleChoices.ORGANIZATION_MEMBER.value])
        self.assertEqual(
            cleaned_data["domain_request_permissions"], UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS.value
        )
        self.assertEqual(cleaned_data["domain_permissions"], UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS.value)
        self.assertEqual(cleaned_data["member_permissions"], UserPortfolioPermissionChoices.VIEW_MEMBERS.value)

        data = {
            "email": "hi@ho.com",
            "portfolio": self.portfolio.id,
            "role": UserPortfolioRoleChoices.ORGANIZATION_MEMBER.value,
            "domain_request_permissions": UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS.value,
            "domain_permissions": UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS.value,
            "member_permissions": UserPortfolioPermissionChoices.VIEW_MEMBERS.value,
        }

        form = self._assert_form_is_valid(PortfolioNewMemberForm, data)
        cleaned_data = form.cleaned_data
        self.assertEqual(cleaned_data["roles"], [UserPortfolioRoleChoices.ORGANIZATION_MEMBER.value])
        self.assertEqual(
            cleaned_data["domain_request_permissions"], UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS.value
        )
        self.assertEqual(cleaned_data["domain_permissions"], UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS.value)
        self.assertEqual(cleaned_data["member_permissions"], UserPortfolioPermissionChoices.VIEW_MEMBERS.value)

    @less_console_noise_decorator
    def test_clean_member_permission_edgecase(self):
        """Test that the clean method correctly handles the special "no_access" value for members.
        We'll need to add a portfolio, which in the app is handled by the view post."""

        user_portfolio_permission, _ = UserPortfolioPermission.objects.get_or_create(
            portfolio=self.portfolio, user=self.user
        )
        portfolio_invitation, _ = PortfolioInvitation.objects.get_or_create(portfolio=self.portfolio, email="hi@ho")

        data = {
            "role": UserPortfolioRoleChoices.ORGANIZATION_MEMBER.value,
            "domain_request_permissions": "no_access",  # Simulate no access permission
            "domain_permissions": UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS.value,
            "member_permissions": UserPortfolioPermissionChoices.VIEW_MEMBERS.value,
        }

        form = self._assert_form_is_valid(PortfolioMemberForm, data, user_portfolio_permission)
        cleaned_data = form.cleaned_data
        self.assertEqual(cleaned_data["domain_request_permissions"], None)

        form = self._assert_form_is_valid(PortfolioInvitedMemberForm, data, portfolio_invitation)
        cleaned_data = form.cleaned_data
        self.assertEqual(cleaned_data["domain_request_permissions"], None)

    @less_console_noise_decorator
    def test_map_instance_to_initial_admin_role(self):
        """Test that instance data is correctly mapped to the initial form values for an admin role."""
        user_portfolio_permission = UserPortfolioPermission(
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
        )
        portfolio_invitation, _ = PortfolioInvitation.objects.get_or_create(
            portfolio=self.portfolio,
            email="hi@ho",
            roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
        )

        expected_initial_data = {
            "role": UserPortfolioRoleChoices.ORGANIZATION_ADMIN,
        }
        self._assert_initial_data(PortfolioMemberForm, user_portfolio_permission, expected_initial_data)
        self._assert_initial_data(PortfolioInvitedMemberForm, portfolio_invitation, expected_initial_data)

    @less_console_noise_decorator
    def test_map_instance_to_initial_member_role(self):
        """Test that instance data is correctly mapped to the initial form values for a member role."""
        user_portfolio_permission = UserPortfolioPermission(
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            additional_permissions=[UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS],
        )
        portfolio_invitation, _ = PortfolioInvitation.objects.get_or_create(
            portfolio=self.portfolio,
            email="hi@ho",
            roles=[UserPortfolioRoleChoices.ORGANIZATION_MEMBER],
            additional_permissions=[UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS],
        )
        expected_initial_data = {
            "role": UserPortfolioRoleChoices.ORGANIZATION_MEMBER,
            "domain_request_permissions": UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS,
        }
        self._assert_initial_data(PortfolioMemberForm, user_portfolio_permission, expected_initial_data)
        self._assert_initial_data(PortfolioInvitedMemberForm, portfolio_invitation, expected_initial_data)

    @less_console_noise_decorator
    def test_invalid_data_for_member(self):
        """Test invalid form submission for a member role with missing permissions."""
        portfolio_invitation, _ = PortfolioInvitation.objects.get_or_create(portfolio=self.portfolio, email="hi@ho")
        data = {
            "email": "hi@ho.com",
            "portfolio": self.portfolio.id,
            "role": UserPortfolioRoleChoices.ORGANIZATION_MEMBER.value,
            "domain_request_permissions": "",  # Missing field
            "member_permissions": "",  # Missing field
            "domain_permissions": "",  # Missing field
        }
        self._assert_form_has_error(PortfolioMemberForm, data, "domain_request_permissions", portfolio_invitation)
        self._assert_form_has_error(PortfolioInvitedMemberForm, data, "member_permissions", portfolio_invitation)
