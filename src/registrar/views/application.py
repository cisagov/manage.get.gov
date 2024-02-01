import logging
from collections import defaultdict
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import resolve, reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from django.contrib import messages

from registrar.forms import application_wizard as forms
from registrar.models import DomainApplication
from registrar.models.contact import Contact
from registrar.models.user import User
from registrar.utility import StrEnum
from registrar.views.utility import StepsHelper
from registrar.views.utility.permission_views import DomainApplicationPermissionDeleteView

from .utility import (
    DomainApplicationPermissionView,
    DomainApplicationPermissionWithdrawView,
    ApplicationWizardPermissionView,
)

logger = logging.getLogger(__name__)


class Step(StrEnum):
    """
    Names for each page of the application wizard.

    As with Django's own `TextChoices` class, steps will
    appear in the order they are defined. (Order matters.)
    """

    ORGANIZATION_TYPE = "organization_type"
    TRIBAL_GOVERNMENT = "tribal_government"
    ORGANIZATION_FEDERAL = "organization_federal"
    ORGANIZATION_ELECTION = "organization_election"
    ORGANIZATION_CONTACT = "organization_contact"
    ABOUT_YOUR_ORGANIZATION = "about_your_organization"
    AUTHORIZING_OFFICIAL = "authorizing_official"
    CURRENT_SITES = "current_sites"
    DOTGOV_DOMAIN = "dotgov_domain"
    PURPOSE = "purpose"
    YOUR_CONTACT = "your_contact"
    OTHER_CONTACTS = "other_contacts"
    ANYTHING_ELSE = "anything_else"
    REQUIREMENTS = "requirements"
    REVIEW = "review"


class ApplicationWizard(ApplicationWizardPermissionView, TemplateView):
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

    template_name = ""

    # uniquely namespace the wizard in urls.py
    # (this is not seen _in_ urls, only for Django's internal naming)
    # NB: this is included here for reference. Do not change it without
    # also changing the many places it is hardcoded in the HTML templates
    URL_NAMESPACE = "application"
    # name for accessing /application/<id>/edit
    EDIT_URL_NAME = "edit-application"
    NEW_URL_NAME = "/request/"
    # We need to pass our human-readable step titles as context to the templates.
    TITLES = {
        Step.ORGANIZATION_TYPE: _("Type of organization"),
        Step.TRIBAL_GOVERNMENT: _("Tribal government"),
        Step.ORGANIZATION_FEDERAL: _("Federal government branch"),
        Step.ORGANIZATION_ELECTION: _("Election office"),
        Step.ORGANIZATION_CONTACT: _("Organization name and mailing address"),
        Step.ABOUT_YOUR_ORGANIZATION: _("About your organization"),
        Step.AUTHORIZING_OFFICIAL: _("Authorizing official"),
        Step.CURRENT_SITES: _("Current websites"),
        Step.DOTGOV_DOMAIN: _(".gov domain"),
        Step.PURPOSE: _("Purpose of your domain"),
        Step.YOUR_CONTACT: _("Your contact information"),
        Step.OTHER_CONTACTS: _("Other employees from your organization"),
        Step.ANYTHING_ELSE: _("Anything else?"),
        Step.REQUIREMENTS: _("Requirements for operating a .gov domain"),
        Step.REVIEW: _("Review and submit your domain request"),
    }

    # We can use a dictionary with step names and callables that return booleans
    # to show or hide particular steps based on the state of the process.
    WIZARD_CONDITIONS = {
        Step.ORGANIZATION_FEDERAL: lambda w: w.from_model("show_organization_federal", False),
        Step.TRIBAL_GOVERNMENT: lambda w: w.from_model("show_tribal_government", False),
        Step.ORGANIZATION_ELECTION: lambda w: w.from_model("show_organization_election", False),
        Step.ABOUT_YOUR_ORGANIZATION: lambda w: w.from_model("show_about_your_organization", False),
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

        # For linter. The else block should never be hit, but if it does,
        # there may be a UI consideration. That will need to be handled in another ticket.
        creator = None
        if self.request.user is not None and isinstance(self.request.user, User):
            creator = self.request.user
        else:
            raise ValueError("Invalid value for User")

        if self.has_pk():
            id = self.storage["application_id"]
            try:
                self._application = DomainApplication.objects.get(
                    creator=creator,
                    pk=id,
                )
                return self._application
            except DomainApplication.DoesNotExist:
                logger.debug("Application id %s did not have a DomainApplication" % id)

        self._application = DomainApplication.objects.create(creator=self.request.user)

        self.storage["application_id"] = self._application.id
        return self._application

    @property
    def storage(self):
        # marking session as modified on every access
        # so that updates to nested keys are always saved
        # Also - check that self.request.session has the attr
        # modified to account for test environments calling
        # view methods
        if hasattr(self.request.session, "modified"):
            self.request.session.modified = True
        return self.request.session.setdefault(self.prefix, {})

    @storage.setter
    def storage(self, value):
        self.request.session[self.prefix] = value
        self.request.session.modified = True

    @storage.deleter
    def storage(self):
        if self.prefix in self.request.session:
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
        # and remove any prior wizard data from their session
        if current_url == self.EDIT_URL_NAME and "id" in kwargs:
            del self.storage
            self.storage["application_id"] = kwargs["id"]

        # if accessing this class directly, redirect to the first step
        #     in other words, if `ApplicationWizard` is called as view
        #     directly by some redirect or url handler, we'll send users
        #     either to an acknowledgement page or to the first step in
        #     the processes (if an edit rather than a new request); subclasses
        #     will NOT be redirected. The purpose of this is to allow code to
        #     send users "to the application wizard" without needing to
        #     know which view is first in the list of steps.
        if self.__class__ == ApplicationWizard:
            if request.path_info == self.NEW_URL_NAME:
                return render(request, "application_intro.html")
            else:
                return self.goto(self.steps.first)

        self.steps.current = current_url
        context = self.get_context_data()
        context["forms"] = self.get_forms()

        # if pending requests exist and user does not have approved domains,
        # present message that domain application cannot be submitted
        pending_requests = self.pending_requests()
        if len(pending_requests) > 0:
            message_header = "You cannot submit this request yet"
            message_content = (
                f"<h4 class='usa-alert__heading'>{message_header}</h4> "
                "<p class='margin-bottom-0'>New domain requests cannot be submitted until we have finished "
                f"reviewing your pending request: <strong>{pending_requests[0].requested_domain}</strong>. "
                "You can continue to fill out this request and save it as a draft to be submitted later. "
                f"<a class='usa-link' href='{reverse('home')}'>View your pending requests.</a></p>"
            )
            context["pending_requests_message"] = mark_safe(message_content)  # nosec

        context["pending_requests_exist"] = len(pending_requests) > 0

        return render(request, self.template_name, context)

    def get_all_forms(self, **kwargs) -> list:
        """
        Calls `get_forms` for all steps and returns a flat list.

        All arguments (**kwargs) are passed directly to `get_forms`.
        """
        nested = (self.get_forms(step=step, **kwargs) for step in self.steps)
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
            if use_post:
                instantiated.append(form(self.request.POST, **kwargs))
            elif use_db:
                instantiated.append(form(data, **kwargs))
            else:
                instantiated.append(form(initial=data, **kwargs))

        return instantiated

    def pending_requests(self):
        """return an array of pending requests if user has pending requests
        and no approved requests"""
        if self.approved_applications_exist() or self.approved_domains_exist():
            return []
        else:
            return self.pending_applications()

    def approved_applications_exist(self):
        """Checks if user is creator of applications with ApplicationStatus.APPROVED status"""
        approved_application_count = DomainApplication.objects.filter(
            creator=self.request.user, status=DomainApplication.ApplicationStatus.APPROVED
        ).count()
        return approved_application_count > 0

    def approved_domains_exist(self):
        """Checks if user has permissions on approved domains

        This additional check is necessary to account for domains which were migrated
        and do not have an application"""
        return self.request.user.permissions.count() > 0

    def pending_applications(self):
        """Returns a List of user's applications with one of the following states:
        ApplicationStatus.SUBMITTED, ApplicationStatus.IN_REVIEW, ApplicationStatus.ACTION_NEEDED"""
        # if the current application has ApplicationStatus.ACTION_NEEDED status, this check should not be performed
        if self.application.status == DomainApplication.ApplicationStatus.ACTION_NEEDED:
            return []
        check_statuses = [
            DomainApplication.ApplicationStatus.SUBMITTED,
            DomainApplication.ApplicationStatus.IN_REVIEW,
            DomainApplication.ApplicationStatus.ACTION_NEEDED,
        ]
        return DomainApplication.objects.filter(creator=self.request.user, status__in=check_statuses)
    
    def db_check_for_unlocking_steps(self):
        """Helper for get_context_data
            
        Queries the DB for an application and returns a dict for unlocked steps."""
        return {
            "organization_type": bool(self.application.organization_type),
            "tribal_government": bool(self.application.tribe_name),
            "organization_federal": bool(self.application.federal_type),
            "organization_election": bool(self.application.is_election_board),
            "organization_contact": (
                bool(self.application.federal_agency) or bool(self.application.organization_name) or
                bool(self.application.address_line1) or bool(self.application.city) or
                bool(self.application.state_territory) or bool(self.application.zipcode) or
                bool(self.application.urbanization)
            ),
            "about_your_organization": bool(self.application.about_your_organization),
            "authorizing_official": bool(self.application.authorizing_official),
            "current_sites": (
                bool(self.application.current_websites.exists()) or bool(self.application.requested_domain)
            ),
            "dotgov_domain": bool(self.application.requested_domain),
            "purpose": bool(self.application.purpose),
            "your_contact": bool(self.application.submitter),
            "other_contacts": (
                bool(self.application.other_contacts.exists()) or bool(self.application.no_other_contacts_rationale)
            ),
            "anything_else": (
                bool(self.application.anything_else) or bool(self.application.is_policy_acknowledged)
            ),
            "requirements": bool(self.application.is_policy_acknowledged),
            "review": bool(self.application.is_policy_acknowledged),
        }

    def get_context_data(self):
        """Define context for access on all wizard pages."""
        # Build the submit button that we'll pass to the modal.
        modal_button = '<button type="submit" ' 'class="usa-button" ' ">Submit request</button>"
        # Concatenate the modal header that we'll pass to the modal.
        if self.application.requested_domain:
            modal_heading = "You are about to submit a domain request for " + str(self.application.requested_domain)
        else:
            modal_heading = "You are about to submit an incomplete request"

        unlocked_steps_list = [key for key, value in self.db_check_for_unlocking_steps().items() if value]

        return {
            "form_titles": self.TITLES,
            "steps": self.steps,
            # Add information about which steps should be unlocked
            "visited": unlocked_steps_list,
            "is_federal": self.application.is_federal(),
            "modal_button": modal_button,
            "modal_heading": modal_heading,
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

    def is_valid(self, forms: list) -> bool:
        """Returns True if all forms in the wizard are valid."""
        are_valid = (form.is_valid() for form in forms)
        return all(are_valid)

    def post(self, request, *args, **kwargs) -> HttpResponse:
        """This method handles POST requests."""

        # which button did the user press?
        button: str = request.POST.get("submit_button", "")

        # if user has acknowledged the intro message
        if button == "intro_acknowledge":
            if request.path_info == self.NEW_URL_NAME:
                del self.storage
            return self.goto(self.steps.first)

        # if accessing this class directly, redirect to the first step
        if self.__class__ == ApplicationWizard:
            return self.goto(self.steps.first)

        forms = self.get_forms(use_post=True)
        if self.is_valid(forms):
            # always save progress
            self.save(forms)
        else:
            context = self.get_context_data()
            context["forms"] = forms
            return render(request, self.template_name, context)

        # if user opted to save their progress,
        # return them to the page they were already on
        if button == "save":
            messages.success(request, "Your progress has been saved!")
            return self.goto(self.steps.current)
        # if user opted to save progress and return,
        # return them to the home page
        if button == "save_and_return":
            return HttpResponseRedirect(reverse("home"))
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


class TribalGovernment(ApplicationWizard):
    template_name = "application_tribal_government.html"
    forms = [forms.TribalGovernmentForm]


class OrganizationFederal(ApplicationWizard):
    template_name = "application_org_federal.html"
    forms = [forms.OrganizationFederalForm]


class OrganizationElection(ApplicationWizard):
    template_name = "application_org_election.html"
    forms = [forms.OrganizationElectionForm]


class OrganizationContact(ApplicationWizard):
    template_name = "application_org_contact.html"
    forms = [forms.OrganizationContactForm]


class AboutYourOrganization(ApplicationWizard):
    template_name = "application_about_your_organization.html"
    forms = [forms.AboutYourOrganizationForm]


class AuthorizingOfficial(ApplicationWizard):
    template_name = "application_authorizing_official.html"
    forms = [forms.AuthorizingOfficialForm]

    def get_context_data(self):
        context = super().get_context_data()
        context["organization_type"] = self.application.organization_type
        context["federal_type"] = self.application.federal_type
        return context


class CurrentSites(ApplicationWizard):
    template_name = "application_current_sites.html"
    forms = [forms.CurrentSitesFormSet]


class DotgovDomain(ApplicationWizard):
    template_name = "application_dotgov_domain.html"
    forms = [forms.DotGovDomainForm, forms.AlternativeDomainFormSet]

    def get_context_data(self):
        context = super().get_context_data()
        context["organization_type"] = self.application.organization_type
        context["federal_type"] = self.application.federal_type
        return context


class Purpose(ApplicationWizard):
    template_name = "application_purpose.html"
    forms = [forms.PurposeForm]


class YourContact(ApplicationWizard):
    template_name = "application_your_contact.html"
    forms = [forms.YourContactForm]


class OtherContacts(ApplicationWizard):
    template_name = "application_other_contacts.html"
    forms = [forms.OtherContactsYesNoForm, forms.OtherContactsFormSet, forms.NoOtherContactsForm]

    def is_valid(self, forms: list) -> bool:
        """Overrides default behavior defined in ApplicationWizard.
        Depending on value in other_contacts_yes_no_form, marks forms in
        other_contacts or no_other_contacts for deletion. Then validates
        all forms.
        """
        other_contacts_yes_no_form = forms[0]
        other_contacts_forms = forms[1]
        no_other_contacts_form = forms[2]

        # set all the required other_contact fields as necessary since new forms
        # were added through javascript
        for form in forms[1].forms:
            for field_item, field in form.fields.items():
                if field.required:
                    field.widget.attrs["required"] = "required"

        all_forms_valid = True
        # test first for yes_no_form validity
        if other_contacts_yes_no_form.is_valid():
            # test for has_contacts
            if other_contacts_yes_no_form.cleaned_data.get("has_other_contacts"):
                # mark the no_other_contacts_form for deletion
                no_other_contacts_form.mark_form_for_deletion()
                # test that the other_contacts_forms and no_other_contacts_forms are valid
                all_forms_valid = all(form.is_valid() for form in forms[1:])
            else:
                # mark the other_contacts_forms formset for deletion
                other_contacts_forms.mark_formset_for_deletion()
                all_forms_valid = all(form.is_valid() for form in forms[1:])
        else:
            # if yes no form is invalid, no choice has been made
            # mark other forms for deletion so that their errors are not
            # returned
            other_contacts_forms.mark_formset_for_deletion()
            no_other_contacts_form.mark_form_for_deletion()
            all_forms_valid = False
        return all_forms_valid


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


class ApplicationStatus(DomainApplicationPermissionView):
    template_name = "application_status.html"


class ApplicationWithdrawConfirmation(DomainApplicationPermissionWithdrawView):
    """This page will ask user to confirm if they want to withdraw

    The DomainApplicationPermissionView restricts access so that only the
    `creator` of the application may withdraw it.
    """

    template_name = "application_withdraw_confirmation.html"


class ApplicationWithdrawn(DomainApplicationPermissionWithdrawView):
    # this view renders no template
    template_name = ""

    def get(self, *args, **kwargs):
        """View class that does the actual withdrawing.

        If user click on withdraw confirm button, this view updates the status
        to withdraw and send back to homepage.
        """
        application = DomainApplication.objects.get(id=self.kwargs["pk"])
        application.withdraw()
        application.save()
        return HttpResponseRedirect(reverse("home"))


class DomainApplicationDeleteView(DomainApplicationPermissionDeleteView):
    """Delete view for home that allows the end user to delete DomainApplications"""

    object: DomainApplication  # workaround for type mismatch in DeleteView

    def has_permission(self):
        """Custom override for has_permission to exclude all statuses, except WITHDRAWN and STARTED"""
        has_perm = super().has_permission()
        if not has_perm:
            return False

        status = self.get_object().status
        valid_statuses = [DomainApplication.ApplicationStatus.WITHDRAWN, DomainApplication.ApplicationStatus.STARTED]
        if status not in valid_statuses:
            return False

        return True

    def get_success_url(self):
        """After a delete is successful, redirect to home"""
        return reverse("home")

    def post(self, request, *args, **kwargs):
        # Grab all orphaned contacts
        application: DomainApplication = self.get_object()
        contacts_to_delete, duplicates = self._get_orphaned_contacts(application)

        # Delete the DomainApplication
        response = super().post(request, *args, **kwargs)

        # Delete orphaned contacts - but only for if they are not associated with a user
        Contact.objects.filter(id__in=contacts_to_delete, user=None).delete()

        # After a delete occurs, do a second sweep on any returned duplicates.
        # This determines if any of these three fields share a contact, which is used for
        # the edge case where the same user may be an AO, and a submitter, for example.
        if len(duplicates) > 0:
            duplicates_to_delete, _ = self._get_orphaned_contacts(application, check_db=True)
            Contact.objects.filter(id__in=duplicates_to_delete, user=None).delete()

        return response

    def _get_orphaned_contacts(self, application: DomainApplication, check_db=False):
        """
        Collects all orphaned contacts associated with a given DomainApplication object.

        An orphaned contact is defined as a contact that is associated with the application,
        but not with any other application. This includes the authorizing official, the submitter,
        and any other contacts linked to the application.

        Parameters:
        application (DomainApplication): The DomainApplication object for which to find orphaned contacts.
        check_db (bool, optional): A flag indicating whether to check the database for the existence of the contacts.
                                Defaults to False.

        Returns:
        tuple: A tuple containing two lists. The first list contains the IDs of the orphaned contacts.
            The second list contains any duplicate contacts found. ([Contacts], [Contacts])
        """
        contacts_to_delete = []

        # Get each contact object on the DomainApplication object
        ao = application.authorizing_official
        submitter = application.submitter
        other_contacts = list(application.other_contacts.all())
        other_contact_ids = application.other_contacts.all().values_list("id", flat=True)

        # Check if the desired item still exists in the DB
        if check_db:
            ao = self._get_contacts_by_id([ao.id]).first() if ao is not None else None
            submitter = self._get_contacts_by_id([submitter.id]).first() if submitter is not None else None
            other_contacts = self._get_contacts_by_id(other_contact_ids)

        # Pair each contact with its db related name for use in checking if it has joins
        checked_contacts = [(ao, "authorizing_official"), (submitter, "submitted_applications")]
        checked_contacts.extend((contact, "contact_applications") for contact in other_contacts)

        for contact, related_name in checked_contacts:
            if contact is not None and not contact.has_more_than_one_join(related_name):
                contacts_to_delete.append(contact.id)

        return (contacts_to_delete, self._get_duplicates(checked_contacts))

    def _get_contacts_by_id(self, contact_ids):
        """Given a list of ids, grab contacts if it exists"""
        contacts = Contact.objects.filter(id__in=contact_ids)
        return contacts

    def _get_duplicates(self, objects):
        """Given a list of objects, return a list of which items were duplicates"""
        # Gets the occurence count
        object_dict = defaultdict(int)
        for contact, _related in objects:
            object_dict[contact] += 1

        duplicates = [item for item, count in object_dict.items() if count > 1]
        return duplicates
