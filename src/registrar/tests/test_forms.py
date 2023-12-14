"""Test form validation requirements."""

from django.test import TestCase, RequestFactory

from registrar.forms.application_wizard import (
    CurrentSitesForm,
    DotGovDomainForm,
    AuthorizingOfficialForm,
    OrganizationContactForm,
    YourContactForm,
    OtherContactsForm,
    RequirementsForm,
    TribalGovernmentForm,
    PurposeForm,
    AnythingElseForm,
    AboutYourOrganizationForm,
)
from registrar.forms.domain import ContactForm
from registrar.tests.common import MockEppLib
from django.contrib.auth import get_user_model


class TestFormValidation(MockEppLib):
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create(username="username")
        self.factory = RequestFactory()

    def test_org_contact_zip_invalid(self):
        form = OrganizationContactForm(data={"zipcode": "nah"})
        self.assertEqual(
            form.errors["zipcode"],
            ["Enter a zip code in the required format, like 12345 or 12345-6789."],
        )

    def test_org_contact_zip_valid(self):
        for zipcode in ["12345", "12345-6789"]:
            form = OrganizationContactForm(data={"zipcode": zipcode})
            self.assertNotIn("zipcode", form.errors)

    def test_website_invalid(self):
        form = CurrentSitesForm(data={"website": "nah"})
        self.assertEqual(
            form.errors["website"],
            ["Enter your organization's current website in the required format, like www.city.com."],
        )

    def test_website_valid(self):
        form = CurrentSitesForm(data={"website": "hyphens-rule.gov.uk"})
        self.assertEqual(len(form.errors), 0)

    def test_website_scheme_valid(self):
        form = CurrentSitesForm(data={"website": "http://hyphens-rule.gov.uk"})
        self.assertEqual(len(form.errors), 0)
        form = CurrentSitesForm(data={"website": "https://hyphens-rule.gov.uk"})
        self.assertEqual(len(form.errors), 0)

    def test_requested_domain_valid(self):
        """Just a valid domain name with no .gov at the end."""
        form = DotGovDomainForm(data={"requested_domain": "top-level-agency"})
        self.assertEqual(len(form.errors), 0)

    def test_requested_domain_ending_dotgov(self):
        """Just a valid domain name with .gov at the end."""
        form = DotGovDomainForm(data={"requested_domain": "top-level-agency.gov"})
        self.assertEqual(len(form.errors), 0)
        self.assertEqual(form.cleaned_data["requested_domain"], "top-level-agency")

    def test_requested_domain_ending_dotcom_invalid(self):
        """don't accept domains ending other than .gov."""
        form = DotGovDomainForm(data={"requested_domain": "top-level-agency.com"})
        self.assertEqual(
            form.errors["requested_domain"],
            ["Enter the .gov domain you want without any periods."],
        )

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

    def test_requested_domain_invalid_characters(self):
        """must be a valid .gov domain name."""
        form = DotGovDomainForm(data={"requested_domain": "underscores_forever"})
        self.assertEqual(
            form.errors["requested_domain"],
            ["Enter a domain using only letters, numbers, or hyphens (though we don't recommend using hyphens)."],
        )

    def test_authorizing_official_email_invalid(self):
        """must be a valid email address."""
        form = AuthorizingOfficialForm(data={"email": "boss@boss"})
        self.assertEqual(
            form.errors["email"],
            ["Enter an email address in the required format, like name@example.com."],
        )

    def test_purpose_form_character_count_invalid(self):
        """Response must be less than 1000 characters."""
        form = PurposeForm(
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
            }
        )
        self.assertEqual(
            form.errors["purpose"],
            ["Response must be less than 1000 characters."],
        )

    def test_anything_else_form_about_your_organization_character_count_invalid(self):
        """Response must be less than 1000 characters."""
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
            }
        )
        self.assertEqual(
            form.errors["anything_else"],
            ["Response must be less than 1000 characters."],
        )

    def test_anything_else_form_character_count_invalid(self):
        """Response must be less than 1000 characters."""
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
            }
        )
        self.assertEqual(
            form.errors["about_your_organization"],
            ["Response must be less than 1000 characters."],
        )

    def test_authorizing_official_phone_invalid(self):
        """Must be a valid phone number."""
        form = AuthorizingOfficialForm(data={"phone": "boss@boss"})
        self.assertTrue(form.errors["phone"][0].startswith("Enter a valid phone number "))

    def test_your_contact_email_invalid(self):
        """must be a valid email address."""
        form = YourContactForm(data={"email": "boss@boss"})
        self.assertEqual(
            form.errors["email"],
            ["Enter your email address in the required format, like name@example.com."],
        )

    def test_your_contact_phone_invalid(self):
        """Must be a valid phone number."""
        form = YourContactForm(data={"phone": "boss@boss"})
        self.assertTrue(form.errors["phone"][0].startswith("Enter a valid phone number "))

    def test_other_contact_email_invalid(self):
        """must be a valid email address."""
        form = OtherContactsForm(data={"email": "boss@boss"})
        self.assertEqual(
            form.errors["email"],
            ["Enter an email address in the required format, like name@example.com."],
        )

    def test_other_contact_phone_invalid(self):
        """Must be a valid phone number."""
        form = OtherContactsForm(data={"phone": "boss@boss"})
        self.assertTrue(form.errors["phone"][0].startswith("Enter a valid phone number "))

    def test_requirements_form_blank(self):
        """Requirements box unchecked is an error."""
        form = RequirementsForm(data={})
        self.assertEqual(
            form.errors["is_policy_acknowledged"],
            ["Check the box if you read and agree to the requirements for operating .gov domains."],
        )

    def test_requirements_form_unchecked(self):
        """Requirements box unchecked is an error."""
        form = RequirementsForm(data={"is_policy_acknowledged": False})
        self.assertEqual(
            form.errors["is_policy_acknowledged"],
            ["Check the box if you read and agree to the requirements for operating .gov domains."],
        )

    def test_tribal_government_unrecognized(self):
        """Not state or federally recognized is an error."""
        form = TribalGovernmentForm(data={"state_recognized": False, "federally_recognized": False})
        self.assertTrue(any("tell us more about your tribe" in error for error in form.non_field_errors()))


class TestContactForm(TestCase):
    def test_contact_form_email_invalid(self):
        form = ContactForm(data={"email": "example.net"})
        self.assertEqual(form.errors["email"], ["Enter a valid email address."])

    def test_contact_form_email_invalid2(self):
        form = ContactForm(data={"email": "@"})
        self.assertEqual(form.errors["email"], ["Enter a valid email address."])
