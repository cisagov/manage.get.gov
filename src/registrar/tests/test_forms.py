"""Test form validation requirements."""

from django.test import TestCase

from registrar.forms.application_wizard import (
    CurrentSitesForm,
    DotGovDomainForm,
    AuthorizingOfficialForm,
    OrganizationContactForm,
    YourContactForm,
    OtherContactsForm,
    SecurityEmailForm,
    RequirementsForm,
)


class TestFormValidation(TestCase):
    def test_org_contact_zip_invalid(self):
        form = OrganizationContactForm(data={"zipcode": "nah"})
        self.assertEqual(
            form.errors["zipcode"],
            ["Enter a zip code in the form of 12345 or 12345-6789."],
        )

    def test_org_contact_zip_valid(self):
        for zipcode in ["12345", "12345-6789"]:
            form = OrganizationContactForm(data={"zipcode": zipcode})
            self.assertNotIn("zipcode", form.errors)

    def test_current_site_invalid(self):
        form = CurrentSitesForm(data={"current_site": "nah"})
        self.assertEqual(
            form.errors["current_site"],
            [
                "Enter your organization’s website in the required format, like"
                " www.city.com."
            ],
        )

    def test_current_site_valid(self):
        form = CurrentSitesForm(data={"current_site": "hyphens-rule.gov.uk"})
        self.assertEqual(len(form.errors), 0)

    def test_current_site_scheme_valid(self):
        form = CurrentSitesForm(data={"current_site": "http://hyphens-rule.gov.uk"})
        self.assertEqual(len(form.errors), 0)
        form = CurrentSitesForm(data={"current_site": "https://hyphens-rule.gov.uk"})
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

    def test_requested_domain_invalid_characters(self):
        """must be a valid .gov domain name."""
        form = DotGovDomainForm(data={"requested_domain": "underscores_forever"})
        self.assertEqual(
            form.errors["requested_domain"],
            [
                "Enter a domain using only letters, numbers, or hyphens (though we"
                " don't recommend using hyphens)."
            ],
        )

    def test_authorizing_official_email_invalid(self):
        """must be a valid email address."""
        form = AuthorizingOfficialForm(data={"email": "boss@boss"})
        self.assertEqual(
            form.errors["email"],
            ["Enter an email address in the required format, like name@example.com."],
        )

    def test_authorizing_official_phone_invalid(self):
        """Must be a valid phone number."""
        form = AuthorizingOfficialForm(data={"phone": "boss@boss"})
        self.assertTrue(
            form.errors["phone"][0].startswith("Enter a valid phone number")
        )

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
        self.assertTrue(
            form.errors["phone"][0].startswith("Enter a valid phone number")
        )

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
        self.assertTrue(
            form.errors["phone"][0].startswith("Enter a valid phone number")
        )

    def test_security_email_form_blank(self):
        """Can leave the security_email field blank."""
        form = SecurityEmailForm(data={})
        self.assertEqual(len(form.errors), 0)

    def test_security_email_form_invalid(self):
        """Can leave the security_email field blank."""
        form = SecurityEmailForm(data={"security_email": "boss@boss"})
        self.assertEqual(
            form.errors["security_email"],
            ["Enter an email address in the required format, like name@example.com."],
        )

    def test_requirements_form_blank(self):
        """Requirements box unchecked is an error."""
        form = RequirementsForm(data={})
        self.assertEqual(
            form.errors["is_policy_acknowledged"],
            [
                "Check the box if you read and agree to the requirements for"
                " registering and operating .gov domains."
            ],
        )

    def test_requirements_form_unchecked(self):
        """Requirements box unchecked is an error."""
        form = RequirementsForm(data={"is_policy_acknowledged": False})
        self.assertEqual(
            form.errors["is_policy_acknowledged"],
            [
                "Check the box if you read and agree to the requirements for"
                " registering and operating .gov domains."
            ],
        )
