"""Forms Wizard for creating a new domain application."""

from __future__ import annotations  # allows forward references in annotations

import logging

from typing import Union

from django import forms
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import resolve

from formtools.wizard.views import NamedUrlSessionWizardView  # type: ignore

from registrar.models import Contact, DomainApplication, Domain


logger = logging.getLogger(__name__)


class RegistrarForm(forms.Form):
    """Subclass used to remove the default colon suffix from all fields."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super(RegistrarForm, self).__init__(*args, **kwargs)

    def to_database(self, obj: DomainApplication | Contact):
        """
        Adds this form's cleaned data to `obj` and saves `obj`.

        Does nothing if form is not valid.
        """
        if not self.is_valid():
            return
        for name, value in self.cleaned_data.items():
            setattr(obj, name, value)
        obj.save()

    def from_database(self, obj: DomainApplication | Contact):
        """Initializes this form's fields with values gotten from `obj`."""
        for name in self.declared_fields.keys():
            self.initial[name] = getattr(obj, name)  # type: ignore


class OrganizationTypeForm(RegistrarForm):
    organization_type = forms.ChoiceField(
        required=True,
        choices=DomainApplication.OrganizationChoices.choices,
        widget=forms.RadioSelect,
    )


class OrganizationFederalForm(RegistrarForm):
    federal_type = forms.ChoiceField(
        choices=DomainApplication.BranchChoices.choices,
        widget=forms.RadioSelect,
    )


class OrganizationElectionForm(RegistrarForm):
    is_election_board = forms.BooleanField(
        widget=forms.RadioSelect(
            choices=[
                (True, "Yes"),
                (False, "No"),
            ],
        ),
    )


class OrganizationContactForm(RegistrarForm):
    # for federal agencies we also want to know the top-level agency.
    federal_agency = forms.ChoiceField(
        label="Federal agency",
        # not required because this field won't be filled out unless
        # it is a federal agency.
        required=False,
        choices=DomainApplication.AGENCY_CHOICES,
    )
    organization_name = forms.CharField(label="Organization Name")
    address_line1 = forms.CharField(label="Street address")
    address_line2 = forms.CharField(
        required=False,
        label="Street address line 2",
    )
    city = forms.CharField(label="City")
    state_territory = forms.ChoiceField(
        label="State, territory, or military post",
        choices=[("", "--Select--")] + DomainApplication.StateTerritoryChoices.choices,
    )
    zipcode = forms.CharField(label="ZIP code")
    urbanization = forms.CharField(label="Urbanization (Puerto Rico only)")


class AuthorizingOfficialForm(RegistrarForm):
    def to_database(self, obj):
        """Adds this form's cleaned data to `obj` and saves `obj`."""
        if not self.is_valid():
            return
        contact = getattr(obj, "authorizing_official", None)
        if contact is not None:
            super().to_database(contact)
        else:
            contact = Contact()
            super().to_database(contact)
            obj.authorizing_official = contact
            obj.save()

    def from_database(self, obj):
        """Initializes this form's fields with values gotten from `obj`."""
        contact = getattr(obj, "authorizing_official", None)
        if contact is not None:
            super().from_database(contact)

    first_name = forms.CharField(label="First name/given name")
    middle_name = forms.CharField(
        required=False,
        label="Middle name (optional)",
    )
    last_name = forms.CharField(label="Last name/family name")
    title = forms.CharField(label="Title or role in your organization")
    email = forms.EmailField(label="Email")
    phone = forms.CharField(label="Phone")


class CurrentSitesForm(RegistrarForm):
    def to_database(self, obj):
        """Adds this form's cleaned data to `obj` and saves `obj`."""
        if not self.is_valid():
            return
        obj.save()
        normalized = Domain.normalize(self.cleaned_data["current_site"], blank=True)
        if normalized:
            # TODO: ability to update existing records
            obj.current_websites.create(website=normalized)

    def from_database(self, obj):
        """Initializes this form's fields with values gotten from `obj`."""
        current_website = obj.current_websites.first()
        if current_website is not None:
            self.initial["current_site"] = current_website.website

    current_site = forms.CharField(
        required=False,
        label="Enter your organization’s public website, if you have one. For example, "
        "www.city.com.",
    )


class DotGovDomainForm(RegistrarForm):
    def to_database(self, obj):
        """Adds this form's cleaned data to `obj` and saves `obj`."""
        if not self.is_valid():
            return
        normalized = Domain.normalize(
            self.cleaned_data["requested_domain"], "gov", blank=True
        )
        if normalized:
            requested_domain = getattr(obj, "requested_domain", None)
            if requested_domain is not None:
                requested_domain.name = normalized
                requested_domain.save()
            else:
                requested_domain = Domain.objects.create(name=normalized)
                obj.requested_domain = requested_domain
                obj.save()

        obj.save()
        normalized = Domain.normalize(
            self.cleaned_data["alternative_domain"], "gov", blank=True
        )
        if normalized:
            # TODO: ability to update existing records
            obj.alternative_domains.create(website=normalized)

    def from_database(self, obj):
        """Initializes this form's fields with values gotten from `obj`."""
        requested_domain = getattr(obj, "requested_domain", None)
        if requested_domain is not None:
            self.initial["requested_domain"] = requested_domain.sld

        alternative_domain = obj.alternative_domains.first()
        if alternative_domain is not None:
            self.initial["alternative_domain"] = alternative_domain.sld

    requested_domain = forms.CharField(label="What .gov domain do you want?")
    alternative_domain = forms.CharField(
        required=False,
        label="Are there other domains you’d like if we can’t give you your first "
        "choice? Entering alternative domains is optional.",
    )


class PurposeForm(RegistrarForm):
    purpose = forms.CharField(label="Purpose", widget=forms.Textarea())


class YourContactForm(RegistrarForm):
    def to_database(self, obj):
        """Adds this form's cleaned data to `obj` and saves `obj`."""
        if not self.is_valid():
            return
        contact = getattr(obj, "submitter", None)
        if contact is not None:
            super().to_database(contact)
        else:
            contact = Contact()
            super().to_database(contact)
            obj.submitter = contact
            obj.save()

    def from_database(self, obj):
        """Initializes this form's fields with values gotten from `obj`."""
        contact = getattr(obj, "submitter", None)
        if contact is not None:
            super().from_database(contact)

    first_name = forms.CharField(label="First name/given name")
    middle_name = forms.CharField(
        required=False,
        label="Middle name (optional)",
    )
    last_name = forms.CharField(label="Last name/family name")
    title = forms.CharField(label="Title or role in your organization")
    email = forms.EmailField(label="Email")
    phone = forms.CharField(label="Phone")


class OtherContactsForm(RegistrarForm):
    def to_database(self, obj):
        """Adds this form's cleaned data to `obj` and saves `obj`."""
        if not self.is_valid():
            return
        obj.save()

        # TODO: ability to handle multiple contacts
        contact = obj.other_contacts.filter(email=self.cleaned_data["email"]).first()
        if contact is not None:
            super().to_database(contact)
        else:
            contact = Contact()
            super().to_database(contact)
            obj.other_contacts.add(contact)

    def from_database(self, obj):
        """Initializes this form's fields with values gotten from `obj`."""
        other_contacts = obj.other_contacts.first()
        if other_contacts is not None:
            super().from_database(other_contacts)

    first_name = forms.CharField(label="First name/given name")
    middle_name = forms.CharField(
        required=False,
        label="Middle name (optional)",
    )
    last_name = forms.CharField(label="Last name/family name")
    title = forms.CharField(label="Title or role in your organization")
    email = forms.EmailField(label="Email")
    phone = forms.CharField(label="Phone")


class SecurityEmailForm(RegistrarForm):
    security_email = forms.EmailField(
        required=False,
        label="Security email",
    )


class AnythingElseForm(RegistrarForm):
    anything_else = forms.CharField(
        required=False,
        label="Anything else we should know",
        widget=forms.Textarea(),
    )


class RequirementsForm(RegistrarForm):
    is_policy_acknowledged = forms.BooleanField(
        label="I read and agree to the .gov domain requirements."
    )


class ReviewForm(RegistrarForm):
    """
    Empty class for the review page.

    It gets included as part of the form, but does not have any form fields itself.
    """

    def to_database(self, _):
        """This form has no data. Do nothing."""
        pass

    pass


class Step:
    """Names for each page of the application wizard."""

    ORGANIZATION_TYPE = "organization_type"
    ORGANIZATION_FEDERAL = "organization_federal"
    ORGANIZATION_ELECTION = "organization_election"
    ORGANIZATION_CONTACT = "organization_contact"
    AUTHORIZING_OFFICIAL = "authorizing_official"
    CURRENT_SITES = "current_sites"
    DOTGOV_DOMAIN = "dotgov_domain"
    PURPOSE = "purpose"
    YOUR_CONTACT = "your_contact"
    OTHER_CONTACTS = "other_contacts"
    SECURITY_EMAIL = "security_email"
    ANYTHING_ELSE = "anything_else"
    REQUIREMENTS = "requirements"
    REVIEW = "review"


# List of forms in our wizard.
# Each entry is a tuple of a name and a form subclass
FORMS = [
    (Step.ORGANIZATION_TYPE, OrganizationTypeForm),
    (Step.ORGANIZATION_FEDERAL, OrganizationFederalForm),
    (Step.ORGANIZATION_ELECTION, OrganizationElectionForm),
    (Step.ORGANIZATION_CONTACT, OrganizationContactForm),
    (Step.AUTHORIZING_OFFICIAL, AuthorizingOfficialForm),
    (Step.CURRENT_SITES, CurrentSitesForm),
    (Step.DOTGOV_DOMAIN, DotGovDomainForm),
    (Step.PURPOSE, PurposeForm),
    (Step.YOUR_CONTACT, YourContactForm),
    (Step.OTHER_CONTACTS, OtherContactsForm),
    (Step.SECURITY_EMAIL, SecurityEmailForm),
    (Step.ANYTHING_ELSE, AnythingElseForm),
    (Step.REQUIREMENTS, RequirementsForm),
    (Step.REVIEW, ReviewForm),
]

# Dict to match up the right template with the right step.
TEMPLATES = {
    Step.ORGANIZATION_TYPE: "application_org_type.html",
    Step.ORGANIZATION_FEDERAL: "application_org_federal.html",
    Step.ORGANIZATION_ELECTION: "application_org_election.html",
    Step.ORGANIZATION_CONTACT: "application_org_contact.html",
    Step.AUTHORIZING_OFFICIAL: "application_authorizing_official.html",
    Step.CURRENT_SITES: "application_current_sites.html",
    Step.DOTGOV_DOMAIN: "application_dotgov_domain.html",
    Step.PURPOSE: "application_purpose.html",
    Step.YOUR_CONTACT: "application_your_contact.html",
    Step.OTHER_CONTACTS: "application_other_contacts.html",
    Step.SECURITY_EMAIL: "application_security_email.html",
    Step.ANYTHING_ELSE: "application_anything_else.html",
    Step.REQUIREMENTS: "application_requirements.html",
    Step.REVIEW: "application_review.html",
}

# We need to pass our page titles as context to the templates
TITLES = {
    Step.ORGANIZATION_TYPE: "Type of organization",
    Step.ORGANIZATION_FEDERAL: "Type of organization — Federal",
    Step.ORGANIZATION_ELECTION: "Type of organization — Election board",
    Step.ORGANIZATION_CONTACT: "Organization name and mailing address",
    Step.AUTHORIZING_OFFICIAL: "Authorizing official",
    Step.CURRENT_SITES: "Organization website",
    Step.DOTGOV_DOMAIN: ".gov domain",
    Step.PURPOSE: "Purpose of your domain",
    Step.YOUR_CONTACT: "Your contact information",
    Step.OTHER_CONTACTS: "Other contacts for your domain",
    Step.SECURITY_EMAIL: "Security email for public use",
    Step.ANYTHING_ELSE: "Anything else we should know?",
    Step.REQUIREMENTS: "Requirements for registration and operation of .gov domains",
    Step.REVIEW: "Review and submit your domain request",
}


# We can use a dictionary with step names and callables that return booleans
# to show or hide particular steps based on the state of the process.
WIZARD_CONDITIONS = {
    "organization_federal": DomainApplication.show_organization_federal,
    "organization_election": DomainApplication.show_organization_election,
}


class ApplicationWizard(LoginRequiredMixin, NamedUrlSessionWizardView):

    """Multi-page form ("wizard") for new domain applications.

    This sets up a sequence of forms that gather information for new
    domain applications. Each form in the sequence has its own URL and
    the progress through the form is stored in the Django session (thus
    "NamedUrlSessionWizardView").

    Caution: due to the redirect performed by using NamedUrlSessionWizardView,
    many methods, such as `process_step`, are called TWICE per request. For
    this reason, methods in this class need to be idempotent.
    """

    form_list = FORMS

    def get_template_names(self):
        """Template for the current step.

        The return is a singleton list.
        """
        return [TEMPLATES[self.steps.current]]

    def _is_federal(self) -> Union[bool, None]:
        """Return whether this application is from a federal agency.

        Returns True if we know that this application is from a federal
        agency, False if we know that it is not and None if there isn't an
        answer yet for that question.
        """
        return self.get_application_object().is_federal()

    def get_context_data(self, form, **kwargs):
        """Add title information to the context for all steps."""
        context = super().get_context_data(form=form, **kwargs)
        context["form_titles"] = TITLES
        if self.steps.current == Step.ORGANIZATION_CONTACT:
            context["is_federal"] = self._is_federal()
        if self.steps.current == Step.REVIEW:
            context["step_cls"] = Step
            application = self.get_application_object()
            context["application"] = application
        return context

    def get_application_object(self) -> DomainApplication:
        """
        Attempt to match the current wizard with a DomainApplication.

        Will create an application if none exists.
        """
        if "application_id" in self.storage.extra_data:
            id = self.storage.extra_data["application_id"]
            try:
                return DomainApplication.objects.get(
                    creator=self.request.user,
                    pk=id,
                )
            except DomainApplication.DoesNotExist:
                logger.debug("Application id %s did not have a DomainApplication" % id)

        application = DomainApplication.objects.create(creator=self.request.user)
        self.storage.extra_data["application_id"] = application.id
        return application

    def form_to_database(self, form: RegistrarForm) -> DomainApplication:
        """
        Unpack the form responses onto the model object properties.

        Saves the application to the database.
        """
        application = self.get_application_object()

        if form is not None and hasattr(form, "to_database"):
            form.to_database(application)

        return application

    def process_step(self, form):
        """
        Hook called on every POST request, if the form is valid.

        Do not manipulate the form data here.
        """
        # save progress
        self.form_to_database(form=form)
        return self.get_form_step_data(form)

    def get_form(self, step=None, data=None, files=None):
        """This method constructs the form for a given step."""
        form = super().get_form(step, data, files)

        # restore from database, but only if a record has already
        # been associated with this wizard instance
        if "application_id" in self.storage.extra_data:
            application = self.get_application_object()
            form.from_database(application)
        return form

    def post(self, *args, **kwargs):
        """This method handles POST requests."""
        step = self.steps.current
        # always call super() first, to do important pre-processing
        rendered = super().post(*args, **kwargs)
        # if user opted to save their progress,
        # return them to the page they were already on
        button = self.request.POST.get("submit_button", None)
        if button == "save":
            return self.render_goto_step(step)
        # otherwise, proceed as normal
        return rendered

    def get(self, *args, **kwargs):
        """This method handles GET requests."""
        current_url = resolve(self.request.path_info).url_name
        # always call super(), it handles important redirect logic
        rendered = super().get(*args, **kwargs)
        # if user visited via an "edit" url, associate the id of the
        # application they are trying to edit to this wizard instance
        if current_url == "edit-application" and "id" in kwargs:
            self.storage.extra_data["application_id"] = kwargs["id"]
        return rendered

    def done(self, form_list, form_dict, **kwargs):
        """Called when the data for every form is submitted and validated."""
        application = self.get_application_object()
        application.submit()  # change the status to submitted
        application.save()
        logger.debug("Application object saved: %s", application.id)
        return render(
            self.request, "application_done.html", {"application_id": application.id}
        )
