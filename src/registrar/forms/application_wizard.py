"""Forms Wizard for creating a new domain application."""

import logging

from django import forms

from formtools.wizard.views import NamedUrlSessionWizardView  # type: ignore


logger = logging.getLogger(__name__)


class RequirementsForm(forms.Form):
    template_name = "application_requirements.html"
    agree_box = forms.BooleanField()


class OrganizationForm(forms.Form):
    template_name = "application_organization.html"
    organization_type = forms.ChoiceField(widget=forms.RadioSelect)


# List of forms in our wizard. Each entry is a tuple of a name and a form
# subclass
FORMS = [("requirements", RequirementsForm), ("organization", OrganizationForm)]

# Dict to match up the right template with the right step. Keys here must
# match the first elements of the tuples above
TEMPLATES = {
    "requirements": "application_requirements.html",
    "organization": "application_organization.html",
}


class ApplicationWizard(NamedUrlSessionWizardView):
    form_list = FORMS

    def get_template_names(self):
        """Template for the current step.

        The return is a singleton list.
        """
        return [TEMPLATES[self.steps.current]]

    def done(self, form_list, **kwargs):
        logger.info("Application form submitted.")
