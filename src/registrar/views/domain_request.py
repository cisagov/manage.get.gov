import logging
from collections import defaultdict
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import resolve, reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from django.contrib import messages

from registrar.forms import domain_request_wizard as forms
from registrar.models import DomainRequest
from registrar.models.contact import Contact
from registrar.models.user import User
from registrar.utility import StrEnum
from registrar.views.utility import StepsHelper
from registrar.views.utility.permission_views import DomainRequestPermissionDeleteView

from .utility import (
    DomainRequestPermissionView,
    DomainRequestPermissionWithdrawView,
    DomainRequestWizardPermissionView,
)

from waffle.decorators import flag_is_active, waffle_flag

logger = logging.getLogger(__name__)


class Step(StrEnum):
    """
    Names for each page of the domain request wizard.

    As with Django's own `TextChoices` class, steps will
    appear in the order they are defined. (Order matters.)
    """

    ORGANIZATION_TYPE = "generic_org_type"
    TRIBAL_GOVERNMENT = "tribal_government"
    ORGANIZATION_FEDERAL = "organization_federal"
    ORGANIZATION_ELECTION = "organization_election"
    ORGANIZATION_CONTACT = "organization_contact"
    ABOUT_YOUR_ORGANIZATION = "about_your_organization"
    SENIOR_OFFICIAL = "senior_official"
    CURRENT_SITES = "current_sites"
    DOTGOV_DOMAIN = "dotgov_domain"
    PURPOSE = "purpose"
    YOUR_CONTACT = "your_contact"
    OTHER_CONTACTS = "other_contacts"
    ADDITIONAL_DETAILS = "additional_details"
    REQUIREMENTS = "requirements"
    REVIEW = "review"


class DomainRequestWizard(DomainRequestWizardPermissionView, TemplateView):
    """
    A common set of methods and configuration.

    The registrar's domain request is several pages of "steps".
    Together, these steps constitute a "wizard".

    This base class sets up a shared state (stored in the user's session)
    between pages of the domain request and provides common methods for
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
    URL_NAMESPACE = "domain-request"
    # name for accessing /domain-request/<id>/edit
    EDIT_URL_NAME = "edit-domain-request"
    NEW_URL_NAME = "/request/"
    # We need to pass our human-readable step titles as context to the templates.
    TITLES = {
        Step.ORGANIZATION_TYPE: _("Type of organization"),
        Step.TRIBAL_GOVERNMENT: _("Tribal government"),
        Step.ORGANIZATION_FEDERAL: _("Federal government branch"),
        Step.ORGANIZATION_ELECTION: _("Election office"),
        Step.ORGANIZATION_CONTACT: _("Organization name and mailing address"),
        Step.ABOUT_YOUR_ORGANIZATION: _("About your organization"),
        Step.SENIOR_OFFICIAL: _("Senior official"),
        Step.CURRENT_SITES: _("Current websites"),
        Step.DOTGOV_DOMAIN: _(".gov domain"),
        Step.PURPOSE: _("Purpose of your domain"),
        Step.YOUR_CONTACT: _("Your contact information"),
        Step.OTHER_CONTACTS: _("Other employees from your organization"),
        Step.ADDITIONAL_DETAILS: _("Additional details"),
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
        self._domain_request = None  # for caching

    def has_pk(self):
        """Does this wizard know about a DomainRequest database record?"""
        return "domain_request_id" in self.storage

    @property
    def prefix(self):
        """Namespace the wizard to avoid clashes in session variable names."""
        # this is a string literal but can be made dynamic if we'd like
        # users to have multiple domain requests open for editing simultaneously
        return "wizard_domain_request"

    @property
    def domain_request(self) -> DomainRequest:
        """
        Attempt to match the current wizard with a DomainRequest.

        Will create a domain request if none exists.
        """
        if self._domain_request:
            return self._domain_request

        # For linter. The else block should never be hit, but if it does,
        # there may be a UI consideration. That will need to be handled in another ticket.
        creator = None
        if self.request.user is not None and isinstance(self.request.user, User):
            creator = self.request.user
        else:
            raise ValueError("Invalid value for User")

        if self.has_pk():
            id = self.storage["domain_request_id"]
            try:
                self._domain_request = DomainRequest.objects.get(
                    creator=creator,
                    pk=id,
                )
                return self._domain_request
            except DomainRequest.DoesNotExist:
                logger.debug("DomainRequest id %s did not have a DomainRequest" % id)

        self._domain_request = DomainRequest.objects.create(creator=self.request.user)

        self.storage["domain_request_id"] = self._domain_request.id
        return self._domain_request

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
        self.domain_request.submit()  # change the status to submitted
        self.domain_request.save()
        logger.debug("Domain Request object saved: %s", self.domain_request.id)
        return redirect(reverse(f"{self.URL_NAMESPACE}:finished"))

    def from_model(self, attribute: str, default, *args, **kwargs):
        """
        Get a attribute from the database model, if it exists.

        If it is a callable, call it with any given `args` and `kwargs`.

        This method exists so that we can avoid needlessly creating a record
        in the database before the wizard has been saved.
        """
        if self.has_pk():
            if hasattr(self.domain_request, attribute):
                attr = getattr(self.domain_request, attribute)
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
        # domain request they are trying to edit to this wizard instance
        # and remove any prior wizard data from their session
        if current_url == self.EDIT_URL_NAME and "id" in kwargs:
            del self.storage
            self.storage["domain_request_id"] = kwargs["id"]

        # if accessing this class directly, redirect to either to an acknowledgement
        # page or to the first step in the processes (if an edit rather than a new request);
        # subclasseswill NOT be redirected. The purpose of this is to allow code to
        # send users "to the domain request wizard" without needing to know which view
        # is first in the list of steps.
        if self.__class__ == DomainRequestWizard:
            if request.path_info == self.NEW_URL_NAME:
                # Clear context so the prop getter won't create a request here.
                # Creating a request will be handled in the post method for the
                # intro page.
                return render(request, "domain_request_intro.html", {})
            else:
                return self.goto(self.steps.first)

        # refresh step_history to ensure we don't erroneously unlock unfinished
        # steps just because we visited it
        self.storage["step_history"] = self.db_check_for_unlocking_steps()
        context = self.get_context_data()
        self.steps.current = current_url
        context["forms"] = self.get_forms()

        # if pending requests exist and user does not have approved domains,
        # present message that domain request cannot be submitted
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
            "domain_request": self.domain_request,  # this is a property, not an object
        }

        if step is None:
            forms = self.forms
        else:
            url = reverse(f"{self.URL_NAMESPACE}:{step}")
            forms = resolve(url).func.view_class.forms

        instantiated = []

        for form in forms:
            data = form.from_database(self.domain_request) if self.has_pk() else None
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
        if self.approved_domain_requests_exist() or self.approved_domains_exist():
            return []
        else:
            return self.pending_domain_requests()

    def approved_domain_requests_exist(self):
        """Checks if user is creator of domain requests with DomainRequestStatus.APPROVED status"""
        approved_domain_request_count = DomainRequest.objects.filter(
            creator=self.request.user, status=DomainRequest.DomainRequestStatus.APPROVED
        ).count()
        return approved_domain_request_count > 0

    def approved_domains_exist(self):
        """Checks if user has permissions on approved domains

        This additional check is necessary to account for domains which were migrated
        and do not have a domain request"""
        return self.request.user.permissions.count() > 0

    def pending_domain_requests(self):
        """Returns a List of user's domain requests with one of the following states:
        DomainRequestStatus.SUBMITTED, DomainRequestStatus.IN_REVIEW, DomainRequestStatus.ACTION_NEEDED"""
        # if the current domain request has DomainRequestStatus.ACTION_NEEDED status, this check should not be performed
        if self.domain_request.status == DomainRequest.DomainRequestStatus.ACTION_NEEDED:
            return []
        check_statuses = [
            DomainRequest.DomainRequestStatus.SUBMITTED,
            DomainRequest.DomainRequestStatus.IN_REVIEW,
            DomainRequest.DomainRequestStatus.ACTION_NEEDED,
        ]
        return DomainRequest.objects.filter(creator=self.request.user, status__in=check_statuses)

    def db_check_for_unlocking_steps(self):
        """Helper for get_context_data

        Queries the DB for a domain request and returns a list of unlocked steps."""

        # The way this works is as follows:
        # Each step is assigned a true/false value to determine if it is
        # "unlocked" or not.  This dictionary of values is looped through
        # at the end of this function and any step with a "true" value is
        # added to a simple array that is returned at the end of this function.
        # This array is eventually passed to the frontend context (eg. domain_request_sidebar.html),
        # and is used to determine how steps appear in the side nav.
        # It is worth noting that any step assigned "false" here will be EXCLUDED
        # from the list of "unlocked" steps.

        history_dict = {
            "generic_org_type": self.domain_request.generic_org_type is not None,
            "tribal_government": self.domain_request.tribe_name is not None,
            "organization_federal": self.domain_request.federal_type is not None,
            "organization_election": self.domain_request.is_election_board is not None,
            "organization_contact": (
                self.domain_request.federal_agency is not None
                or self.domain_request.organization_name is not None
                or self.domain_request.address_line1 is not None
                or self.domain_request.city is not None
                or self.domain_request.state_territory is not None
                or self.domain_request.zipcode is not None
                or self.domain_request.urbanization is not None
            ),
            "about_your_organization": self.domain_request.about_your_organization is not None,
            "senior_official": self.domain_request.senior_official is not None,
            "current_sites": (
                self.domain_request.current_websites.exists() or self.domain_request.requested_domain is not None
            ),
            "dotgov_domain": self.domain_request.requested_domain is not None,
            "purpose": self.domain_request.purpose is not None,
            "your_contact": self.domain_request.submitter is not None,
            "other_contacts": (
                self.domain_request.other_contacts.exists()
                or self.domain_request.no_other_contacts_rationale is not None
            ),
            "additional_details": (
                # Additional details is complete as long as "has anything else" and "has cisa rep" are not None
                (
                    self.domain_request.has_anything_else_text is not None
                    and self.domain_request.has_cisa_representative is not None
                )
            ),
            "requirements": self.domain_request.is_policy_acknowledged is not None,
            "review": self.domain_request.is_policy_acknowledged is not None,
        }
        return [key for key, value in history_dict.items() if value]

    def get_context_data(self):
        """Define context for access on all wizard pages."""

        context_stuff = {}
        if DomainRequest._form_complete(self.domain_request, self.request):
            modal_button = '<button type="submit" ' 'class="usa-button" ' ">Submit request</button>"
            context_stuff = {
                "not_form": False,
                "form_titles": self.TITLES,
                "steps": self.steps,
                "visited": self.storage.get("step_history", []),
                "is_federal": self.domain_request.is_federal(),
                "modal_button": modal_button,
                "modal_heading": "You are about to submit a domain request for "
                + str(self.domain_request.requested_domain),
                "modal_description": "Once you submit this request, you won’t be able to edit it until we review it.\
                You’ll only be able to withdraw your request.",
                "review_form_is_complete": True,
                "user": self.request.user,
            }
        else:  # form is not complete
            modal_button = '<button type="button" class="usa-button" data-close-modal>Return to request</button>'
            context_stuff = {
                "not_form": True,
                "form_titles": self.TITLES,
                "steps": self.steps,
                "visited": self.storage.get("step_history", []),
                "is_federal": self.domain_request.is_federal(),
                "modal_button": modal_button,
                "modal_heading": "Your request form is incomplete",
                "modal_description": 'This request cannot be submitted yet.\
                Return to the request and visit the steps that are marked as "incomplete."',
                "review_form_is_complete": False,
                "user": self.request.user,
            }
        return context_stuff

    def get_step_list(self) -> list:
        """Dynamically generated list of steps in the form wizard."""
        step_list = []
        for step in Step:
            condition = self.WIZARD_CONDITIONS.get(step, True)
            if callable(condition):
                condition = condition(self)
            if condition:
                step_list.append(step)

        if flag_is_active(self.request, "profile_feature"):
            step_list.remove(Step.YOUR_CONTACT)

        return step_list

    def goto(self, step):
        if step == "generic_org_type":
            # We need to avoid creating a new domain request if the user
            # clicks the back button
            self.request.session["new_request"] = False
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
        # If a user hits the new request url directly
        if "new_request" not in request.session:
            request.session["new_request"] = True
        # if user has acknowledged the intro message
        if button == "intro_acknowledge":
            if request.path_info == self.NEW_URL_NAME:

                if self.request.session["new_request"] is True:
                    # This will trigger the domain_request getter into creating a new DomainRequest
                    del self.storage

            return self.goto(self.steps.first)

        # if accessing this class directly, redirect to the first step
        if self.__class__ == DomainRequestWizard:
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

        Saves the domain request to the database.
        """
        for form in forms:
            if form is not None and hasattr(form, "to_database"):
                form.to_database(self.domain_request)


class OrganizationType(DomainRequestWizard):
    template_name = "domain_request_org_type.html"
    forms = [forms.OrganizationTypeForm]


class TribalGovernment(DomainRequestWizard):
    template_name = "domain_request_tribal_government.html"
    forms = [forms.TribalGovernmentForm]


class OrganizationFederal(DomainRequestWizard):
    template_name = "domain_request_org_federal.html"
    forms = [forms.OrganizationFederalForm]


class OrganizationElection(DomainRequestWizard):
    template_name = "domain_request_org_election.html"
    forms = [forms.OrganizationElectionForm]


class OrganizationContact(DomainRequestWizard):
    template_name = "domain_request_org_contact.html"
    forms = [forms.OrganizationContactForm]


class AboutYourOrganization(DomainRequestWizard):
    template_name = "domain_request_about_your_organization.html"
    forms = [forms.AboutYourOrganizationForm]


class SeniorOfficial(DomainRequestWizard):
    template_name = "domain_request_senior_official.html"
    forms = [forms.SeniorOfficialForm]

    def get_context_data(self):
        context = super().get_context_data()
        context["generic_org_type"] = self.domain_request.generic_org_type
        context["federal_type"] = self.domain_request.federal_type
        return context


class CurrentSites(DomainRequestWizard):
    template_name = "domain_request_current_sites.html"
    forms = [forms.CurrentSitesFormSet]


class DotgovDomain(DomainRequestWizard):
    template_name = "domain_request_dotgov_domain.html"
    forms = [forms.DotGovDomainForm, forms.AlternativeDomainFormSet]

    def get_context_data(self):
        context = super().get_context_data()
        context["generic_org_type"] = self.domain_request.generic_org_type
        context["federal_type"] = self.domain_request.federal_type
        return context


class Purpose(DomainRequestWizard):
    template_name = "domain_request_purpose.html"
    forms = [forms.PurposeForm]


class YourContact(DomainRequestWizard):
    template_name = "domain_request_your_contact.html"
    forms = [forms.YourContactForm]

    @waffle_flag("!profile_feature")  # type: ignore
    def dispatch(self, request, *args, **kwargs):  # type: ignore
        return super().dispatch(request, *args, **kwargs)


class OtherContacts(DomainRequestWizard):
    template_name = "domain_request_other_contacts.html"
    forms = [forms.OtherContactsYesNoForm, forms.OtherContactsFormSet, forms.NoOtherContactsForm]

    def is_valid(self, forms: list) -> bool:
        """Overrides default behavior defined in DomainRequestWizard.
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


class AdditionalDetails(DomainRequestWizard):

    template_name = "domain_request_additional_details.html"

    forms = [
        forms.CisaRepresentativeYesNoForm,
        forms.CisaRepresentativeForm,
        forms.AnythingElseYesNoForm,
        forms.AnythingElseForm,
    ]

    def is_valid(self, forms: list) -> bool:

        # Validate Cisa Representative
        """Overrides default behavior defined in DomainRequestWizard.
        Depending on value in yes_no forms, marks corresponding data
        for deletion. Then validates all forms.
        """
        cisa_representative_email_yes_no_form = forms[0]
        cisa_representative_email_form = forms[1]
        anything_else_yes_no_form = forms[2]
        anything_else_form = forms[3]

        # ------- Validate cisa representative -------
        cisa_rep_portion_is_valid = True
        # test first for yes_no_form validity
        if cisa_representative_email_yes_no_form.is_valid():
            # test for existing data
            if not cisa_representative_email_yes_no_form.cleaned_data.get("has_cisa_representative"):
                # mark the cisa_representative_email_form for deletion
                cisa_representative_email_form.mark_form_for_deletion()
            else:
                cisa_rep_portion_is_valid = cisa_representative_email_form.is_valid()
        else:
            # if yes no form is invalid, no choice has been made
            # mark the cisa_representative_email_form for deletion
            cisa_representative_email_form.mark_form_for_deletion()
            cisa_rep_portion_is_valid = False

        # ------- Validate anything else -------
        anything_else_portion_is_valid = True
        # test first for yes_no_form validity
        if anything_else_yes_no_form.is_valid():
            # test for existing data
            if not anything_else_yes_no_form.cleaned_data.get("has_anything_else_text"):
                # mark the anything_else_form for deletion
                anything_else_form.mark_form_for_deletion()
            else:
                anything_else_portion_is_valid = anything_else_form.is_valid()
        else:
            # if yes no form is invalid, no choice has been made
            # mark the anything_else_form for deletion
            anything_else_form.mark_form_for_deletion()
            anything_else_portion_is_valid = False

        # ------- Return combined validation result -------
        all_forms_valid = cisa_rep_portion_is_valid and anything_else_portion_is_valid
        return all_forms_valid


class Requirements(DomainRequestWizard):
    template_name = "domain_request_requirements.html"
    forms = [forms.RequirementsForm]


class Review(DomainRequestWizard):
    template_name = "domain_request_review.html"
    forms = []  # type: ignore

    def get_context_data(self):
        if DomainRequest._form_complete(self.domain_request, self.request) is False:
            logger.warning("User arrived at review page with an incomplete form.")
        context = super().get_context_data()
        context["Step"] = Step.__members__
        context["domain_request"] = self.domain_request
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


class Finished(DomainRequestWizard):
    template_name = "domain_request_done.html"
    forms = []  # type: ignore

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        context["domain_request_id"] = self.domain_request.id
        # clean up this wizard session, because we are done with it
        del self.storage
        return render(self.request, self.template_name, context)


class DomainRequestStatus(DomainRequestPermissionView):
    template_name = "domain_request_status.html"


class DomainRequestWithdrawConfirmation(DomainRequestPermissionWithdrawView):
    """This page will ask user to confirm if they want to withdraw

    The DomainRequestPermissionView restricts access so that only the
    `creator` of the domain request may withdraw it.
    """

    template_name = "domain_request_withdraw_confirmation.html"


class DomainRequestWithdrawn(DomainRequestPermissionWithdrawView):
    # this view renders no template
    template_name = ""

    def get(self, *args, **kwargs):
        """View class that does the actual withdrawing.

        If user click on withdraw confirm button, this view updates the status
        to withdraw and send back to homepage.
        """
        domain_request = DomainRequest.objects.get(id=self.kwargs["pk"])
        domain_request.withdraw()
        domain_request.save()
        return HttpResponseRedirect(reverse("home"))


class DomainRequestDeleteView(DomainRequestPermissionDeleteView):
    """Delete view for home that allows the end user to delete DomainRequests"""

    object: DomainRequest  # workaround for type mismatch in DeleteView

    def has_permission(self):
        """Custom override for has_permission to exclude all statuses, except WITHDRAWN and STARTED"""
        has_perm = super().has_permission()
        if not has_perm:
            return False

        status = self.get_object().status
        valid_statuses = [DomainRequest.DomainRequestStatus.WITHDRAWN, DomainRequest.DomainRequestStatus.STARTED]
        if status not in valid_statuses:
            return False

        return True

    def get_success_url(self):
        """After a delete is successful, redirect to home"""
        return reverse("home")

    def post(self, request, *args, **kwargs):
        # Grab all orphaned contacts
        domain_request: DomainRequest = self.get_object()
        contacts_to_delete, duplicates = self._get_orphaned_contacts(domain_request)

        # Delete the DomainRequest
        self.object = self.get_object()
        self.object.delete()

        # Delete orphaned contacts
        Contact.objects.filter(id__in=contacts_to_delete).delete()

        # After a delete occurs, do a second sweep on any returned duplicates.
        # This determines if any of these three fields share a contact, which is used for
        # the edge case where the same user may be an SO, and a submitter, for example.
        if len(duplicates) > 0:
            duplicates_to_delete, _ = self._get_orphaned_contacts(domain_request, check_db=True)
            Contact.objects.filter(id__in=duplicates_to_delete).delete()

        # Return a 200 response with an empty body
        return HttpResponse(status=200)

    def _get_orphaned_contacts(self, domain_request: DomainRequest, check_db=False):
        """
        Collects all orphaned contacts associated with a given DomainRequest object.

        An orphaned contact is defined as a contact that is associated with the domain request,
        but not with any other domain_request. This includes the senior official, the submitter,
        and any other contacts linked to the domain_request.

        Parameters:
        domain_request (DomainRequest): The DomainRequest object for which to find orphaned contacts.
        check_db (bool, optional): A flag indicating whether to check the database for the existence of the contacts.
                                Defaults to False.

        Returns:
        tuple: A tuple containing two lists. The first list contains the IDs of the orphaned contacts.
            The second list contains any duplicate contacts found. ([Contacts], [Contacts])
        """
        contacts_to_delete = []

        # Get each contact object on the DomainRequest object
        so = domain_request.senior_official
        submitter = domain_request.submitter
        other_contacts = list(domain_request.other_contacts.all())
        other_contact_ids = domain_request.other_contacts.all().values_list("id", flat=True)

        # Check if the desired item still exists in the DB
        if check_db:
            so = self._get_contacts_by_id([so.id]).first() if so is not None else None
            submitter = self._get_contacts_by_id([submitter.id]).first() if submitter is not None else None
            other_contacts = self._get_contacts_by_id(other_contact_ids)

        # Pair each contact with its db related name for use in checking if it has joins
        checked_contacts = [(so, "senior_official"), (submitter, "submitted_domain_requests")]
        checked_contacts.extend((contact, "contact_domain_requests") for contact in other_contacts)

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
