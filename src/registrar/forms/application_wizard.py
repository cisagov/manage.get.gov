"""Forms Wizard for creating a new domain application."""

import logging

from django import forms

from django.contrib.auth.mixins import LoginRequiredMixin

from formtools.wizard.views import NamedUrlSessionWizardView  # type: ignore


logger = logging.getLogger(__name__)


class OrganizationForm(forms.Form):
    organization_type = forms.ChoiceField(
        required=True,
        choices=[
            ("Federal", "Federal: a federal agency"),
            ("Interstate", "Interstate: an organization of two or more states"),
            (
                "State_or_Territory",
                (
                    "State or Territory: One of the 50 U.S. states, the District of "
                    "Columbia, American Samoa, Guam, Northern Mariana Islands, "
                    "Puerto Rico, or the U.S. Virgin Islands"
                ),
            ),
            (
                "Tribal",
                (
                    "Tribal: a tribal government recognized by the federal or "
                    "state government"
                ),
            ),
            ("County", "County: a county, parish, or borough"),
            ("City", "City: a city, town, township, village, etc."),
            (
                "Special_District",
                "Special District: an independent organization within a single state",
            ),
        ],
        widget=forms.RadioSelect,
    )
    federal_type = forms.ChoiceField(
        required=False,
        choices=[
            ("Executive", "Executive"),
            ("Judicial", "Judicial"),
            ("Legislative", "Legislative"),
        ],
        widget=forms.RadioSelect,
    )
    is_election_board = forms.ChoiceField(
        required=False,
        choices=[
            ("Yes", "Yes"),
            ("No", "No"),
        ],
        widget=forms.RadioSelect,
    )


class OrgContactForm(forms.Form):
    organization_name = forms.CharField(label="Organization Name")
    address_line1 = forms.CharField(label="Address line 1")
    address_line2 = forms.CharField(
            required=False,
            label="Address line 2",
            )
    us_state = forms.CharField(label="State")
    zipcode = forms.CharField(label="ZIP code")

class AuthorizingOfficialForm(forms.Form):
    given_name = forms.CharField(label="First name/given name")
    middle_name = forms.CharField(
            required=False,
            label="Middle name (optional)",
            )
    family_name = forms.CharField(label="Last name/family name")
    title = forms.CharField(label="Title or role in your organization")
    email = forms.EmailField(label="Email")
    phone = forms.CharField(label="Phone")

class CurrentSitesForm(forms.Form):
    current_site = forms.CharField(
            required=False,
            label="Enter your organization’s public website, if you have one. For example, www.city.com.")

class DotGovDomainForm(forms.Form):
    dotgov_domain = forms.CharField(label="What .gov domain do you want?")
    alternative_domain = forms.CharField(
            required = False,
            label="Are there other domains you’d like if we can’t give you your first choice? Entering alternative domains is optional.",
            )

class PurposeForm(forms.Form):
    purpose_field = forms.CharField(label="Purpose", widget=forms.Textarea())

class YourContactForm(forms.Form):
    given_name = forms.CharField(label="First name/given name")
    middle_name = forms.CharField(
            required=False,
            label="Middle name (optional)",
            )
    family_name = forms.CharField(label="Last name/family name")
    title = forms.CharField(label="Title or role in your organization")
    email = forms.EmailField(label="Email")
    phone = forms.CharField(label="Phone")


# List of forms in our wizard. Each entry is a tuple of a name and a form
# subclass
FORMS = [
    ("organization", OrganizationForm),
    ("org_contact", OrgContactForm),
    ("authorizing_official", AuthorizingOfficialForm),
    ("current_sites", CurrentSitesForm),
    ("dotgov_domain", DotGovDomainForm),
    ("purpose", PurposeForm),
    ("your_contact", YourContactForm),
]

# Dict to match up the right template with the right step. Keys here must
# match the first elements of the tuples in FORMS
TEMPLATES = {
    "organization": "application_organization.html",
    "org_contact": "application_org_contact.html",
    "authorizing_official": "application_authorizing_official.html",
    "current_sites": "application_current_sites.html",
    "dotgov_domain": "application_dotgov_domain.html",
    "purpose": "application_purpose.html",
    "your_contact": "application_your_contact.html",
}

# We need to pass our page titles as context to the templates, indexed
# by the step names
TITLES = {
    "organization": "Type of organization",
    "org_contact": "Organization name and mailing address",
    "authorizing_official": "Authorizing official",
    "current_sites": "Organization website",
    "dotgov_domain": ".gov domain",
    "purpose": "Purpose of your domain",
    "your_contact": "Your contact information",
}


class ApplicationWizard(LoginRequiredMixin, NamedUrlSessionWizardView):

    """Multi-page form ("wizard") for new domain applications.

    This sets up a sequence of forms that gather information for new
    domain applications. Each form in the sequence has its own URL and
    the progress through the form is stored in the Django session (thus
    "NamedUrlSessionWizardView").
    """

    form_list = FORMS

    def get_template_names(self):
        """Template for the current step.

        The return is a singleton list.
        """
        return [TEMPLATES[self.steps.current]]

    def get_context_data(self, form, **kwargs):
        """Add title information to the context for all steps."""
        context = super().get_context_data(form=form, **kwargs)
        context["form_titles"] = TITLES
        return context

    def done(self, form_list, **kwargs):
        logger.info("Application form submitted.")
