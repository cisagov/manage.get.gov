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


class ContactForm(forms.Form):
    organization_name = forms.CharField(label="Organization Name")
    street_address = forms.CharField(label="Street address")

class PurposeForm(forms.Form):
    purpose_field = forms.CharField(label="Purpose", widget=forms.Textarea(
        attrs={ 'class':'usa-textarea usa-character-count__field',
               'id':'with-hint',
               'aria-describedby':'instructions',
               'maxlength':'500',
            }))

# List of forms in our wizard. Each entry is a tuple of a name and a form
# subclass
FORMS = [
    ("organization", OrganizationForm),
    ("contact", ContactForm),
    ("purpose", PurposeForm),
]

# Dict to match up the right template with the right step. Keys here must
# match the first elements of the tuples in FORMS
TEMPLATES = {
    "organization": "application_organization.html",
    "contact": "application_contact.html",
    "purpose": "application_purpose.html",
}

# We need to pass our page titles as context to the templates, indexed
# by the step names
TITLES = {
    "organization": "About your organization",
    "contact": "Your organization's contact information",
    "purpose": "Purpose of your domain",
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
