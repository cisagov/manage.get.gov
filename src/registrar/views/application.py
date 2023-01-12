import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from registrar.forms import application_wizard as forms
from registrar.models import DomainApplication
from registrar.utility import StrEnum
from registrar.views.utility import StepsHelper

logger = logging.getLogger(__name__)


class Step(StrEnum):
    """
    Names for each page of the application wizard.

    As with Django's own `TextChoices` class, steps will
    appear in the order they are defined. (Order matters.)
    """

    ORGANIZATION_TYPE = "organization_type"
    ORGANIZATION_FEDERAL = "organization_federal"
    ORGANIZATION_ELECTION = "organization_election"
    ORGANIZATION_CONTACT = "organization_contact"
    TYPE_OF_WORK = "type_of_work"
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


class ApplicationWizard(LoginRequiredMixin, TemplateView):
    """
    A common set of methods and configuration.

    The registrar's domain application is several pages of "steps".
    Together, these steps constitute a "wizard".

    This base class sets up a shared state (stored in the user's session)
    between pages of the application and provides common methods for
    processing form data.

    Views for each step should inherit from this base class.

    Any method not marked as internal can be overridden in a subclass,
    although not without consulting the base implementation, first.
    """

    # uniquely namespace the wizard in urls.py
    # (this is not seen _in_ urls, only for Django's internal naming)
    # NB: this is included here for reference. Do not change it without
    # also changing the many places it is hardcoded in the HTML templates
    URL_NAMESPACE = "application"
    # name for accessing /application/<id>/edit
    EDIT_URL_NAME = "edit-application"

    # We need to pass our human-readable step titles as context to the templates.
    TITLES = {
        Step.ORGANIZATION_TYPE: _("Type of organization"),
        Step.ORGANIZATION_FEDERAL: _("Type of organization — Federal"),
        Step.ORGANIZATION_ELECTION: _("Type of organization — Election board"),
        Step.ORGANIZATION_CONTACT: _("Organization name and mailing address"),
        Step.TYPE_OF_WORK: _("Type of Work"),
        Step.AUTHORIZING_OFFICIAL: _("Authorizing official"),
        Step.CURRENT_SITES: _("Organization website"),
        Step.DOTGOV_DOMAIN: _(".gov domain"),
        Step.PURPOSE: _("Purpose of your domain"),
        Step.YOUR_CONTACT: _("Your contact information"),
        Step.OTHER_CONTACTS: _("Other contacts for your domain"),
        Step.SECURITY_EMAIL: _("Security email for public use"),
        Step.ANYTHING_ELSE: _("Anything else we should know?"),
        Step.REQUIREMENTS: _(
            "Requirements for registration and operation of .gov domains"
        ),
        Step.REVIEW: _("Review and submit your domain request"),
    }

    # We can use a dictionary with step names and callables that return booleans
    # to show or hide particular steps based on the state of the process.
    WIZARD_CONDITIONS = {
        Step.ORGANIZATION_FEDERAL: lambda w: w.from_model(
            "show_organization_federal", False
        ),
        Step.ORGANIZATION_ELECTION: lambda w: w.from_model(
            "show_organization_election", False
        ),
        Step.TYPE_OF_WORK: lambda w: w.from_model("show_type_of_work", False),
    }

    def __init__(self):
        super().__init__()
        self.steps = StepsHelper(self)
        self._application = None  # for caching

    def has_pk(self):
        """Does this wizard know about a DomainApplication database record?"""
        return "application_id" in self.storage

    @property
    def prefix(self):
        """Namespace the wizard to avoid clashes in session variable names."""
        # this is a string literal but can be made dynamic if we'd like
        # users to have multiple applications open for editing simultaneously
        return "wizard_application"

    @property
    def application(self) -> DomainApplication:
        """
        Attempt to match the current wizard with a DomainApplication.

        Will create an application if none exists.
        """
        if self._application:
            return self._application

        if self.has_pk():
            id = self.storage["application_id"]
            try:
                self._application = DomainApplication.objects.get(
                    creator=self.request.user,  # type: ignore
                    pk=id,
                )
                return self._application
            except DomainApplication.DoesNotExist:
                logger.debug("Application id %s did not have a DomainApplication" % id)

        self._application = DomainApplication.objects.create(
            creator=self.request.user,  # type: ignore
        )
        self.storage["application_id"] = self._application.id
        return self._application

    @property
    def storage(self):
        # marking session as modified on every access
        # so that updates to nested keys are always saved
        self.request.session.modified = True
        return self.request.session.setdefault(self.prefix, {})

    @storage.setter
    def storage(self, value):
        self.request.session[self.prefix] = value
        self.request.session.modified = True

    @storage.deleter
    def storage(self):
        del self.request.session[self.prefix]
        self.request.session.modified = True

    def done(self):
        """Called when the user clicks the submit button, if all forms are valid."""
        self.application.submit()  # change the status to submitted
        self.application.save()
        logger.debug("Application object saved: %s", self.application.id)
        return redirect(reverse(f"{self.URL_NAMESPACE}:finished"))

    def from_model(self, attribute: str, default, *args, **kwargs):
        """
        Get a attribute from the database model, if it exists.

        If it is a callable, call it with any given `args` and `kwargs`.

        This method exists so that we can avoid needlessly creating a record
        in the database before the wizard has been saved.
        """
        if self.has_pk():
            if hasattr(self.application, attribute):
                attr = getattr(self.application, attribute)
                if callable(attr):
                    return attr(*args, **kwargs)
                else:
                    return attr
            else:
                raise AttributeError("Model has no attribute %s" % str(attribute))
        else:
            return default

    def get(self, request, *args, **kwargs):
        """This method handles GET requests."""

        current_url = resolve(request.path_info).url_name

        # if user visited via an "edit" url, associate the id of the
        # application they are trying to edit to this wizard instance
        if current_url == self.EDIT_URL_NAME and "id" in kwargs:
            self.storage["application_id"] = kwargs["id"]

        # if accessing this class directly, redirect to the first step
        #     in other words, if `ApplicationWizard` is called as view
        #     directly by some redirect or url handler, we'll send users
        #     to the first step in the processes; subclasses will NOT
        #     be redirected. The purpose of this is to allow code to
        #     send users "to the application wizard" without needing to
        #     know which view is first in the list of steps.
        if self.__class__ == ApplicationWizard:
            return self.goto(self.steps.first)

        self.steps.current = current_url
        context = self.get_context_data()
        context["forms"] = self.get_forms()

        return render(request, self.template_name, context)

    def get_all_forms(self) -> list:
        """Calls `get_forms` for all steps and returns a flat list."""
        nested = (self.get_forms(step=step, use_db=True) for step in self.steps)
        flattened = [form for lst in nested for form in lst]
        return flattened

    def get_forms(self, step=None, use_post=False, use_db=False, files=None):
        """
        This method constructs the forms for a given step.

        The form's initial data will always be gotten from the database,
        via the form's `from_database` classmethod.

        The form's bound data will be gotten from POST if `use_post` is True,
        and from the database if `use_db` is True (provided that record exists).
        An empty form will be provided if neither of those are true.
        """

        kwargs = {
            "files": files,
            "prefix": self.steps.current,
            "application": self.application,  # this is a property, not an object
        }

        if step is None:
            forms = self.forms
        else:
            url = reverse(f"{self.URL_NAMESPACE}:{step}")
            forms = resolve(url).func.view_class.forms

        instantiated = []

        for form in forms:
            data = form.from_database(self.application) if self.has_pk() else None
            kwargs["initial"] = data
            if use_post:
                kwargs["data"] = self.request.POST
            elif use_db:
                kwargs["data"] = data
            else:
                kwargs["data"] = None
            instantiated.append(form(**kwargs))

        return instantiated

    def get_context_data(self):
        """Define context for access on all wizard pages."""
        return {
            "form_titles": self.TITLES,
            "steps": self.steps,
            # Add information about which steps should be unlocked
            "visited": self.storage.get("step_history", []),
        }

    def get_step_list(self) -> list:
        """Dynamically generated list of steps in the form wizard."""
        step_list = []
        for step in Step:
            condition = self.WIZARD_CONDITIONS.get(step, True)
            if callable(condition):
                condition = condition(self)
            if condition:
                step_list.append(step)
        return step_list

    def goto(self, step):
        self.steps.current = step
        return redirect(reverse(f"{self.URL_NAMESPACE}:{step}"))

    def goto_next_step(self):
        """Redirects to the next step."""
        next = self.steps.next
        if next:
            self.steps.current = next
            return self.goto(next)
        else:
            raise Http404()

    def is_valid(self, forms: list = None) -> bool:
        """Returns True if all forms in the wizard are valid."""
        forms = forms if forms is not None else self.get_all_forms()
        are_valid = (form.is_valid() for form in forms)
        return all(are_valid)

    def post(self, request, *args, **kwargs):
        """This method handles POST requests."""
        # if accessing this class directly, redirect to the first step
        if self.__class__ == ApplicationWizard:
            return self.goto(self.steps.first)

        forms = self.get_forms(use_post=True)
        if self.is_valid(forms):
            # always save progress
            self.save(forms)
        else:
            # unless there are errors
            context = self.get_context_data()
            context["forms"] = forms
            return render(request, self.template_name, context)

        # if user opted to save their progress,
        # return them to the page they were already on
        button = request.POST.get("submit_button", None)
        if button == "save":
            return self.goto(self.steps.current)
        # otherwise, proceed as normal
        return self.goto_next_step()

    def save(self, forms: list):
        """
        Unpack the form responses onto the model object properties.

        Saves the application to the database.
        """
        for form in forms:
            if form is not None and hasattr(form, "to_database"):
                form.to_database(self.application)


class OrganizationType(ApplicationWizard):
    template_name = "application_org_type.html"
    forms = [forms.OrganizationTypeForm]


class OrganizationFederal(ApplicationWizard):
    template_name = "application_org_federal.html"
    forms = [forms.OrganizationFederalForm]


class OrganizationElection(ApplicationWizard):
    template_name = "application_org_election.html"
    forms = [forms.OrganizationElectionForm]


class OrganizationContact(ApplicationWizard):
    template_name = "application_org_contact.html"
    forms = [forms.OrganizationContactForm]

    def get_context_data(self):
        context = super().get_context_data()
        context["is_federal"] = self.application.is_federal()
        return context


class TypeOfWork(ApplicationWizard):
    template_name = "application_type_of_work.html"
    forms = [forms.TypeOfWorkForm]


class AuthorizingOfficial(ApplicationWizard):
    template_name = "application_authorizing_official.html"
    forms = [forms.AuthorizingOfficialForm]


class CurrentSites(ApplicationWizard):
    template_name = "application_current_sites.html"
    forms = [forms.CurrentSitesForm]


class DotgovDomain(ApplicationWizard):
    template_name = "application_dotgov_domain.html"
    forms = [forms.DotGovDomainForm]


class Purpose(ApplicationWizard):
    template_name = "application_purpose.html"
    forms = [forms.PurposeForm]


class YourContact(ApplicationWizard):
    template_name = "application_your_contact.html"
    forms = [forms.YourContactForm]


class OtherContacts(ApplicationWizard):
    template_name = "application_other_contacts.html"
    forms = [forms.OtherContactsForm]


class SecurityEmail(ApplicationWizard):
    template_name = "application_security_email.html"
    forms = [forms.SecurityEmailForm]


class AnythingElse(ApplicationWizard):
    template_name = "application_anything_else.html"
    forms = [forms.AnythingElseForm]


class Requirements(ApplicationWizard):
    template_name = "application_requirements.html"
    forms = [forms.RequirementsForm]


class Review(ApplicationWizard):
    template_name = "application_review.html"
    forms = []  # type: ignore

    def get_context_data(self):
        context = super().get_context_data()
        context["Step"] = Step.__members__
        context["application"] = self.application
        return context

    def goto_next_step(self):
        return self.done()
        # TODO: validate before saving, show errors
        # Extra info:
        #
        # Formtools used saved POST data to revalidate each form as
        # the user had entered it. This implementation (in this file) discards
        # that data and tries to instantiate the forms from the database
        # in order to perform validation.
        #
        # This must be possible in Django (after all, that is how ModelForms work),
        # but is presently not working: the form claims it is invalid,
        # even when careful checking via breakpoint() shows that the form
        # object contains valid data.
        #
        # forms = self.get_all_forms()
        # if self.is_valid(forms):
        #     return self.done()
        # else:
        #     # TODO: errors to let users know why this isn't working
        #     return self.goto(self.steps.current)


class Finished(ApplicationWizard):
    template_name = "application_done.html"
    forms = []  # type: ignore

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        context["application_id"] = self.application.id
        # clean up this wizard session, because we are done with it
        del self.storage
        return render(self.request, self.template_name, context)
