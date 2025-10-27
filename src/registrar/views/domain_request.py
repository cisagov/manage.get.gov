import logging
from datetime import date
from collections import defaultdict
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import resolve, reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.views.generic import DeleteView, DetailView, TemplateView
from registrar.decorators import (
    HAS_DOMAIN_REQUESTS_VIEW_ALL,
    HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT,
    IS_DOMAIN_REQUEST_REQUESTER,
    grant_access,
)
from registrar.forms import domain_request_wizard as forms
from registrar.forms import feb
from registrar.forms.utility.wizard_form_helper import request_step_list
from registrar.models import DomainRequest
from registrar.models.contact import Contact
from registrar.models.user import User
from registrar.views.utility import StepsHelper
from registrar.utility.enums import Step, PortfolioDomainRequestStep
from registrar.views.utility.invitation_helper import get_org_membership
from ..utility.email import send_templated_email, EmailSendingError

logger = logging.getLogger(__name__)


@grant_access(IS_DOMAIN_REQUEST_REQUESTER, HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT)
class DomainRequestWizard(TemplateView):
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
    is_portfolio = False

    # uniquely namespace the wizard in urls.py
    # (this is not seen _in_ urls, only for Django's internal naming)
    # NB: this is included here for reference. Do not change it without
    # also changing the many places it is hardcoded in the HTML templates
    URL_NAMESPACE = "domain-request"
    # name for accessing /domain-request/<domain_request_pk>/edit
    EDIT_URL_NAME = "edit-domain-request"
    NEW_URL_NAME = "start"
    FINISHED_URL_NAME = "finished"

    # region: Titles
    # We need to pass our human-readable step titles as context to the templates.
    REGULAR_TITLES = {
        Step.ORGANIZATION_TYPE: _("Type of organization"),
        Step.TRIBAL_GOVERNMENT: _("Tribal government"),
        Step.ORGANIZATION_FEDERAL: _("Federal government branch"),
        Step.ORGANIZATION_ELECTION: _("Election office"),
        Step.ORGANIZATION_CONTACT: _("Organization"),
        Step.ABOUT_YOUR_ORGANIZATION: _("About your organization"),
        Step.SENIOR_OFFICIAL: _("Senior official"),
        Step.CURRENT_SITES: _("Current websites"),
        Step.DOTGOV_DOMAIN: _(".gov domain"),
        Step.PURPOSE: _("Purpose of your domain"),
        Step.OTHER_CONTACTS: _("Other employees from your organization"),
        Step.ADDITIONAL_DETAILS: _("Additional details"),
        Step.REQUIREMENTS: _("Requirements for operating a .gov domain"),
        Step.REVIEW: _("Review and submit your domain request"),
    }

    # Titles for the portfolio context
    PORTFOLIO_TITLES = {
        PortfolioDomainRequestStep.REQUESTING_ENTITY: _("Requesting entity"),
        PortfolioDomainRequestStep.DOTGOV_DOMAIN: _(".gov domain"),
        PortfolioDomainRequestStep.PURPOSE: _("Purpose of your domain"),
        PortfolioDomainRequestStep.ADDITIONAL_DETAILS: _("Additional details"),
        PortfolioDomainRequestStep.REQUIREMENTS: _("Requirements for operating a .gov domain"),
        PortfolioDomainRequestStep.REVIEW: _("Review and submit your domain request"),
    }
    # endregion

    # region: Wizard conditions
    # We can use a dictionary with step names and callables that return booleans
    # to show or hide particular steps based on the state of the process.
    REGULAR_WIZARD_CONDITIONS = {
        Step.ORGANIZATION_FEDERAL: lambda w: w.from_model("show_organization_federal", False),
        Step.TRIBAL_GOVERNMENT: lambda w: w.from_model("show_tribal_government", False),
        Step.ORGANIZATION_ELECTION: lambda w: w.from_model("show_organization_election", False),
        Step.ABOUT_YOUR_ORGANIZATION: lambda w: w.from_model("show_about_your_organization", False),
    }

    PORTFOLIO_WIZARD_CONDITIONS = {}  # type: ignore
    # endregion

    # region: Unlocking steps
    # The conditions by which each step is "unlocked" or "locked"
    REGULAR_UNLOCKING_STEPS = {
        Step.ORGANIZATION_TYPE: lambda self: self.domain_request.generic_org_type is not None,
        Step.TRIBAL_GOVERNMENT: lambda self: self.domain_request.tribe_name is not None,
        Step.ORGANIZATION_FEDERAL: lambda self: self.domain_request.federal_type is not None,
        Step.ORGANIZATION_ELECTION: lambda self: self.domain_request.is_election_board is not None,
        Step.ORGANIZATION_CONTACT: lambda self: self.from_model("unlock_organization_contact", False),
        Step.ABOUT_YOUR_ORGANIZATION: lambda self: self.domain_request.about_your_organization is not None,
        Step.SENIOR_OFFICIAL: lambda self: self.domain_request.senior_official is not None,
        Step.CURRENT_SITES: lambda self: (
            self.domain_request.current_websites.exists() or self.domain_request.senior_official is not None
        ),
        Step.DOTGOV_DOMAIN: lambda self: self.domain_request.requested_domain is not None,
        Step.PURPOSE: lambda self: self.domain_request.purpose is not None,
        Step.OTHER_CONTACTS: lambda self: self.from_model("unlock_other_contacts", False),
        Step.ADDITIONAL_DETAILS: lambda self: (
            # Additional details is complete as long as "has anything else" and "has cisa rep" are not None
            (
                self.domain_request.has_anything_else_text is not None
                and self.domain_request.has_cisa_representative is not None
            )
        ),
        Step.REQUIREMENTS: lambda self: self.domain_request.is_policy_acknowledged is not None,
        Step.REVIEW: lambda self: self.domain_request.is_policy_acknowledged is not None,
    }

    PORTFOLIO_UNLOCKING_STEPS = {
        PortfolioDomainRequestStep.REQUESTING_ENTITY: lambda w: w.from_model("unlock_requesting_entity", False),
        PortfolioDomainRequestStep.DOTGOV_DOMAIN: lambda self: self.domain_request.requested_domain is not None,
        PortfolioDomainRequestStep.PURPOSE: lambda self: self.domain_request.purpose is not None,
        PortfolioDomainRequestStep.ADDITIONAL_DETAILS: lambda self: self.domain_request.anything_else is not None,
        PortfolioDomainRequestStep.REQUIREMENTS: lambda self: self.domain_request.is_policy_acknowledged is not None,
        PortfolioDomainRequestStep.REVIEW: lambda self: self.domain_request.is_policy_acknowledged is not None,
    }
    # endregion

    def __init__(self):
        super().__init__()
        self.titles = {}
        self.wizard_conditions = {}
        self.unlocking_steps = {}
        self.steps = None
        # Configure titles, wizard_conditions, unlocking_steps, and steps
        self.configure_step_options()
        self._domain_request = None  # for caching
        self.kwargs = {}

    def configure_step_options(self):
        """Changes which steps are available to the user based on self.is_portfolio.
        This may change on the fly, so we need to evaluate it on the fly.

        Using this information, we then set three configuration variables.
        - self.titles => Returns the page titles for each step
        - self.wizard_conditions => Conditionally shows / hides certain steps
        - self.unlocking_steps => Determines what steps are locked/unlocked

        Then, we create self.steps.
        """
        if self.is_portfolio:
            self.titles = self.PORTFOLIO_TITLES
            self.wizard_conditions = self.PORTFOLIO_WIZARD_CONDITIONS
            self.unlocking_steps = self.PORTFOLIO_UNLOCKING_STEPS
        else:
            self.titles = self.REGULAR_TITLES
            self.wizard_conditions = self.REGULAR_WIZARD_CONDITIONS
            self.unlocking_steps = self.REGULAR_UNLOCKING_STEPS
        self.steps = StepsHelper(self)

    def has_pk(self):
        """Does this wizard know about a DomainRequest database record?"""
        return bool(self.kwargs.get("domain_request_pk") is not None)

    def get_step_enum(self):
        """Determines which step enum we should use for the wizard"""
        return PortfolioDomainRequestStep if self.is_portfolio else Step

    def requires_feb_questions(self) -> bool:
        portfolio = self.request.session.get("portfolio")
        if portfolio:
            return self.domain_request.is_feb()
        return False

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
        requester = None
        if self.request.user is not None and isinstance(self.request.user, User):
            requester = self.request.user
        else:
            raise ValueError("Invalid value for User")

        if self.has_pk():
            try:
                self._domain_request = DomainRequest.objects.get(
                    requester=requester,
                    pk=self.kwargs.get("domain_request_pk"),
                )
                return self._domain_request
            except DomainRequest.DoesNotExist:
                logger.debug("DomainRequest id %s did not have a DomainRequest" % self.kwargs.get("domain_request_pk"))

        # If a user is creating a request, we assume that perms are handled upstream
        if self.request.user.is_org_user(self.request):
            portfolio = self.request.session.get("portfolio")
            self._domain_request = DomainRequest.objects.create(
                requester=self.request.user,
                portfolio=portfolio,
            )
            if portfolio and not self._domain_request.generic_org_type:
                self._domain_request.generic_org_type = portfolio.organization_type
                self._domain_request.save()
        else:
            self._domain_request = DomainRequest.objects.create(requester=self.request.user)
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
        # Notify OMB if an FEB request has been submitted
        if self.requires_feb_questions():
            # Automatically put domain request in review omb if the request is in enteprise mode
            if self.domain_request.portfolio:
                self.domain_request.allow_omb_in_review_transition()
                self.domain_request.save()
            try:
                self.send_omb_submission_email()
            except Exception:
                logger.warning(self.domain_request, "Could not send email confirmation to OMB.")
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

        self.kwargs = kwargs
        if self.request.user.is_org_user(request):
            self.is_portfolio = True
            # Configure titles, wizard_conditions, unlocking_steps, and steps
            self.configure_step_options()

        current_url = resolve(request.path_info).url_name

        # if user visited via an "edit" url, associate the pk of the
        # domain request they are trying to edit to this wizard instance
        # and remove any prior wizard data from their session
        if current_url == self.EDIT_URL_NAME and "domain_request_pk" in kwargs:
            del self.storage

        # if accessing this class directly, redirect to either to an acknowledgement
        # page or to the first step in the processes (if an edit rather than a new request);
        # subclasseswill NOT be redirected. The purpose of this is to allow code to
        # send users "to the domain request wizard" without needing to know which view
        # is first in the list of steps.
        if self.__class__ == DomainRequestWizard:
            if current_url == self.NEW_URL_NAME:
                # Clear context so the prop getter won't create a request here.
                # Creating a request will be handled in the post method for the
                # intro page.
                return render(request, "domain_request_intro.html")
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
        portfolio = self.request.session.get("portfolio")
        _, member_of_this_org = get_org_membership(portfolio, self.request.user.email, self.request.user)
        if not member_of_this_org and len(pending_requests) > 0:
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
        """Checks if user is requester of domain requests with DomainRequestStatus.APPROVED status"""
        approved_domain_request_count = DomainRequest.objects.filter(
            requester=self.request.user, status=DomainRequest.DomainRequestStatus.APPROVED
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
        return DomainRequest.objects.filter(requester=self.request.user, status__in=check_statuses)

    def db_check_for_unlocking_steps(self):
        """Helper for get_context_data.
        Queries the DB for a domain request and returns a list of unlocked steps."""
        return [key for key, is_unlocked_checker in self.unlocking_steps.items() if is_unlocked_checker(self)]

    def form_is_complete(self):
        """Determines if all required steps in the domain request form are complete.
        Returns:
            bool: True if all required steps are complete, False otherwise
        """
        # 1. Get all steps visibly present to the user (required steps)
        # 2. Return every possible step that is "unlocked" (even hidden, conditional ones)
        # 3. Narrows down the list to remove hidden conditional steps
        required_steps = set(self.steps.all)
        unlockable_steps = {step.value for step in self.db_check_for_unlocking_steps()}
        unlocked_steps = {step for step in required_steps if step in unlockable_steps}
        return required_steps == unlocked_steps

    def get_context_data(self):
        """Define context for access on all wizard pages."""
        requested_domain_name = None
        if self.domain_request.requested_domain is not None:
            requested_domain_name = self.domain_request.requested_domain.name

        context = {}
        org_steps_complete = self.form_is_complete()
        if org_steps_complete:
            context = {
                "form_titles": self.titles,
                "steps": self.steps,
                "visited": self.storage.get("step_history", []),
                "is_federal": self.domain_request.is_federal(),
                "review_form_is_complete": True,
                "user": self.request.user,
                "requested_domain__name": requested_domain_name,
            }
        else:  # form is not complete
            context = {
                "form_titles": self.titles,
                "steps": self.steps,
                "visited": self.storage.get("step_history", []),
                "is_federal": self.domain_request.is_federal(),
                "review_form_is_complete": False,
                "user": self.request.user,
                "requested_domain__name": requested_domain_name,
            }
        context["domain_request_id"] = self.domain_request.id
        return context

    def get_step_list(self) -> list:
        """Dynamically generated list of steps in the form wizard."""
        return request_step_list(self, self.get_step_enum())

    def goto(self, step):
        self.steps.current = step
        return redirect(reverse(f"{self.URL_NAMESPACE}:{step}", kwargs={"domain_request_pk": self.domain_request.id}))

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
        if not self.is_portfolio and self.request.user.is_org_user(request):  # type: ignore
            self.is_portfolio = True
            # Configure titles, wizard_conditions, unlocking_steps, and steps
            self.configure_step_options()

        # which button did the user press?
        button: str = request.POST.get("submit_button", "")

        # if user has acknowledged the intro message
        if button == "intro_acknowledge":
            # Split into a function: C901 'DomainRequestWizard.post' is too complex (11)
            self.handle_intro_acknowledge(request)

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

        if button == "back":
            return self.goto(self.steps.prev)
        # if user opted to save their progress,
        # return them to the page they were already on
        if button == "save":
            messages.success(request, "Your progress has been saved!")
            return self.goto(self.steps.current)
        # if user opted to save progress and return,
        # return them to the home page
        if button == "save_and_return":
            if request.user.is_org_user(request):
                return HttpResponseRedirect(reverse("domain-requests"))
            else:
                return HttpResponseRedirect(reverse("home"))

        # otherwise, proceed as normal
        return self.goto_next_step()

    def handle_intro_acknowledge(self, request):
        """If we are starting a new request, clear storage
        and redirect to the first step"""
        return self.goto(self.steps.first)

    def save(self, forms: list):
        """
        Unpack the form responses onto the model object properties.

        Saves the domain request to the database.
        """
        for form in forms:
            if form is not None and hasattr(form, "to_database"):
                form.to_database(self.domain_request)


# TODO - this is a WIP until the domain request experience for portfolios is complete
class PortfolioDomainRequestWizard(DomainRequestWizard):
    is_portfolio = True


# Portfolio pages
class RequestingEntity(DomainRequestWizard):
    template_name = "domain_request_requesting_entity.html"
    forms = [forms.RequestingEntityYesNoForm, forms.RequestingEntityForm]

    def save(self, forms: list):
        """Override of save to clear or associate certain suborganization data
        depending on what the user wishes to do. For instance, we want to add a suborganization
        if the user selects one."""

        # Get the yes/no dropdown value
        yesno_form = forms[0]
        yesno_cleaned_data = yesno_form.cleaned_data
        requesting_entity_is_suborganization = yesno_cleaned_data.get("requesting_entity_is_suborganization")

        # Get the suborg value, and the requested suborg value
        requesting_entity_form = forms[1]
        cleaned_data = requesting_entity_form.cleaned_data
        sub_organization = cleaned_data.get("sub_organization")
        requested_suborganization = cleaned_data.get("requested_suborganization")

        # Do some data cleanup, depending on what option was checked
        if requesting_entity_is_suborganization and (sub_organization or requested_suborganization):
            # Cleanup the organization name field, as this isn't for suborganizations.
            requesting_entity_form.cleaned_data.update({"organization_name": None})
        else:
            # If the user doesn't intend to create a suborg, simply don't make one and do some data cleanup
            requesting_entity_form.cleaned_data.update(
                {
                    "organization_name": (
                        self.domain_request.portfolio.organization_name if self.domain_request.portfolio else None
                    ),
                    "sub_organization": None,
                    "requested_suborganization": None,
                    "suborganization_city": None,
                    "suborganization_state_territory": None,
                }
            )
        super().save(forms)


class PortfolioAdditionalDetails(DomainRequestWizard):
    template_name = "portfolio_domain_request_additional_details.html"

    forms = [
        feb.FEBAnythingElseYesNoForm,
        forms.PortfolioAnythingElseForm,
    ]

    def get_context_data(self):
        context = super().get_context_data()
        context["requires_feb_questions"] = self.requires_feb_questions()
        return context

    def is_valid(self, forms: list) -> bool:
        """
        Validates the forms for portfolio additional details.

        Expected order of forms_list:
            0: FEBAnythingElseYesNoForm
            1: PortfolioAnythingElseForm
        """
        feb_anything_else_yes_no_form = forms[0]
        portfolio_anything_else_form = forms[1]

        if not self.requires_feb_questions():
            for i in range(1):
                forms[i].mark_form_for_deletion()
            # If FEB questions aren't required, validate only the anything else form
            return feb_anything_else_yes_no_form.is_valid()
        anything_else_forms_valid = True
        if not portfolio_anything_else_form.is_valid():
            feb_anything_else_yes_no_form.mark_form_for_deletion()
            anything_else_forms_valid = False
        if portfolio_anything_else_form.cleaned_data.get("has_anything_else_text"):
            feb_anything_else_yes_no_form.fields["anything_else"].required = True
            feb_anything_else_yes_no_form.fields["anything_else"].error_messages[
                "required"
            ] = "Please provide additional details you'd like us to know. \
                If you have nothing to add, select 'No'."
            anything_else_forms_valid = feb_anything_else_yes_no_form.is_valid()
        return anything_else_forms_valid


# Non-portfolio pages
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
    forms = [
        forms.DotGovDomainForm,
        forms.AlternativeDomainFormSet,
        feb.ExecutiveNamingRequirementsYesNoForm,
        feb.ExecutiveNamingRequirementsDetailsForm,
    ]

    def get_context_data(self):
        context = super().get_context_data()
        context["generic_org_type"] = self.domain_request.generic_org_type
        context["federal_type"] = self.domain_request.federal_type
        context["requires_feb_questions"] = self.requires_feb_questions()
        return context

    def is_valid(self, forms_list: list) -> bool:
        """
        Expected order of forms_list:
          0: DotGovDomainForm
          1: AlternativeDomainFormSet
          2: ExecutiveNamingRequirementsYesNoForm
          3: ExecutiveNamingRequirementsDetailsForm
        """
        logger.debug("Validating dotgov domain form")
        # If FEB questions aren't required, validate only non-FEB forms
        if not self.requires_feb_questions():
            forms_list[2].mark_form_for_deletion()
            forms_list[3].mark_form_for_deletion()
            return forms_list[0].is_valid() and forms_list[1].is_valid()

        if not forms_list[2].is_valid():
            logger.debug("Dotgov domain form is invalid")
            # mark details form for deletion so that its errors don't show up
            forms_list[3].mark_form_for_deletion()
            return False

        if forms_list[2].cleaned_data.get("feb_naming_requirements", None):
            logger.debug("Marking details form for deletion")
            # If the user selects "yes" or has made no selection, no details are needed.
            forms_list[3].mark_form_for_deletion()
            valid = all(form.is_valid() for i, form in enumerate(forms_list) if i != 3)
        else:
            # "No" was selected – details are required.
            valid = all(form.is_valid() for form in forms_list)
        return valid


class Purpose(DomainRequestWizard):
    template_name = "domain_request_purpose.html"

    forms = [
        feb.FEBPurposeOptionsForm,
        forms.PurposeDetailsForm,
        feb.FEBTimeFrameYesNoForm,
        feb.FEBTimeFrameDetailsForm,
        feb.FEBInteragencyInitiativeYesNoForm,
        feb.FEBInteragencyInitiativeDetailsForm,
    ]

    def get_context_data(self):
        context = super().get_context_data()
        context["requires_feb_questions"] = self.requires_feb_questions()
        return context

    def is_valid(self, forms_list: list) -> bool:
        """
        Expected order of forms_list:
          0: FEBPurposeOptionsForm
          1: PurposeDetailsForm
          2: FEBTimeFrameYesNoForm
          3: FEBTimeFrameDetailsForm
          4: FEBInteragencyInitiativeYesNoForm
          5: FEBInteragencyInitiativeDetailsForm
        """

        feb_purpose_options_form = forms_list[0]
        purpose_details_form = forms_list[1]
        feb_timeframe_yes_no_form = forms_list[2]
        feb_timeframe_details_form = forms_list[3]
        feb_initiative_yes_no_form = forms_list[4]
        feb_initiative_details_form = forms_list[5]

        if not self.requires_feb_questions():
            # if FEB questions don't apply, mark those forms for deletion
            feb_purpose_options_form.mark_form_for_deletion()
            feb_timeframe_yes_no_form.mark_form_for_deletion()
            feb_timeframe_details_form.mark_form_for_deletion()
            feb_initiative_yes_no_form.mark_form_for_deletion()
            feb_initiative_details_form.mark_form_for_deletion()
            # we only care about the purpose details form in this case since it's used in both instances
            return purpose_details_form.is_valid()

        if feb_purpose_options_form.is_valid():
            option = feb_purpose_options_form.cleaned_data.get("feb_purpose_choice")
            if option == "new":
                purpose_details_form.fields["purpose"].error_messages = {
                    "required": "Provide details on why a new domain is required."
                }
            elif option == "redirect":
                purpose_details_form.fields["purpose"].error_messages = {
                    "required": "Provide details on why a redirect is necessary."
                }
            elif option == "other":
                purpose_details_form.fields["purpose"].error_messages = {
                    "required": "Provide details on how this domain will be used."
                }
            # If somehow none of these are true use the default error message
        else:
            # Ensure details form doesn't throw errors if it's not showing
            purpose_details_form.mark_form_for_deletion()

        feb_timeframe_valid = feb_timeframe_yes_no_form.is_valid()
        feb_initiative_valid = feb_initiative_yes_no_form.is_valid()

        if not feb_timeframe_valid or not feb_timeframe_yes_no_form.cleaned_data.get("has_timeframe"):
            # Ensure details form doesn't throw errors if it's not showing
            feb_timeframe_details_form.mark_form_for_deletion()

        if not feb_initiative_valid or not feb_initiative_yes_no_form.cleaned_data.get("is_interagency_initiative"):
            # Ensure details form doesn't throw errors if it's not showing
            feb_initiative_details_form.mark_form_for_deletion()

        valid = all(form.is_valid() for form in forms_list if not form.form_data_marked_for_deletion)

        return valid


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

    def get_context_data(self):
        context = super().get_context_data()
        context["requires_feb_questions"] = self.requires_feb_questions()
        return context

    # Override the get_forms method to set the policy acknowledgement label conditionally based on feb status
    def get_forms(self, step=None, use_post=False, use_db=False, files=None):
        forms_list = super().get_forms(step, use_post, use_db, files)

        # Pass the is_federal context to the form
        for form in forms_list:
            if isinstance(form, forms.RequirementsForm):
                form.fields["is_policy_acknowledged"].label = (
                    "I read and agree to the requirements for operating a .gov domain."  # noqa: E501
                )

        return forms_list


class Review(DomainRequestWizard):
    template_name = "domain_request_review.html"
    forms = []  # type: ignore

    def get_context_data(self):
        form_complete = self.form_is_complete()
        if form_complete is False:
            logger.warning("User arrived at review page with an incomplete form.")
        context = super().get_context_data()
        context["Step"] = self.get_step_enum().__members__
        context["domain_request"] = self.domain_request
        context["request"] = self.request
        context["requires_feb_questions"] = self.requires_feb_questions()
        context["purpose_label"] = DomainRequest.FEBPurposeChoices.get_purpose_label(
            self.domain_request.feb_purpose_choice
        )
        return context

    def goto_next_step(self):
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

        return self.done()

    def send_omb_submission_email(self):
        """Send a notification to OMB that a domain request has been submitted.
        Uses omb_submission_confirmation.txt template.
        """
        is_analyst_action = (
            "analyst_action" in self.request.session and "analyst_action_location" in self.request.session
        )
        if is_analyst_action:
            logger.debug("No notification sent: Action was conducted by an analyst")
            return

        try:
            purpose_label = DomainRequest.FEBPurposeChoices.get_purpose_label(self.domain_request.feb_purpose_choice)
            # requires_feb_questions and purpose_label used to pass into portfolio_domain_request_summary template
            context = {
                "domain_request": self.domain_request,
                "date": date.today(),
                "requires_feb_questions": True,
                "purpose_label": purpose_label,
            }

            send_templated_email(
                "emails/omb_submission_confirmation.txt",
                "emails/omb_submission_confirmation_subject.txt",
                "ombdotgov@omb.eop.gov",
                context=context,
            )
            logger.info("A submission confirmation email was sent to ombdotgov@omb.eop.gov")
        except EmailSendingError as err:
            logger.error(
                "Failed to send OMB submission confirmation email:\n"
                f"  Subject template: omb_submission_confirmation_subject.txt\n"
                f"  To: ombdotgov@omb.eop.gov\n"
                f"  Error: {err}",
                exc_info=True,
            )


class Finished(DomainRequestWizard):
    template_name = "domain_request_done.html"
    forms = []  # type: ignore

    def get(self, request, *args, **kwargs):
        # clean up this wizard session, because we are done with it
        del self.storage
        return render(self.request, self.template_name)


@grant_access(IS_DOMAIN_REQUEST_REQUESTER, HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT)
class DomainRequestStatus(DetailView):
    template_name = "domain_request_status.html"
    model = DomainRequest
    pk_url_kwarg = "domain_request_pk"
    context_object_name = "DomainRequest"

    def get_context_data(self, **kwargs):
        """Context override to add a step list to the context"""
        context = super().get_context_data(**kwargs)
        # Create a temp wizard object to grab the step list
        if self.request.user.is_org_user(self.request):
            wizard = PortfolioDomainRequestWizard()
            wizard.request = self.request
            context["Step"] = PortfolioDomainRequestStep.__members__
            context["steps"] = request_step_list(wizard, PortfolioDomainRequestStep)
            context["form_titles"] = wizard.titles
        return context


@grant_access(IS_DOMAIN_REQUEST_REQUESTER, HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT)
class DomainRequestWithdrawConfirmation(DetailView):
    """This page will ask user to confirm if they want to withdraw

    Access is restricted so that only the
    `requester` of the domain request may withdraw it.
    """

    template_name = "domain_request_withdraw_confirmation.html"  # DetailView property for what model this is viewing
    model = DomainRequest
    pk_url_kwarg = "domain_request_pk"
    context_object_name = "DomainRequest"


@grant_access(IS_DOMAIN_REQUEST_REQUESTER, HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT)
class DomainRequestWithdrawn(DetailView):
    # this view renders no template
    template_name = ""
    model = DomainRequest
    pk_url_kwarg = "domain_request_pk"
    context_object_name = "DomainRequest"

    def get(self, *args, **kwargs):
        """View class that does the actual withdrawing.

        If user click on withdraw confirm button, this view updates the status
        to withdraw and send back to homepage.
        """
        domain_request = DomainRequest.objects.get(id=self.kwargs["domain_request_pk"])
        domain_request.withdraw()
        domain_request.save()
        if self.request.user.is_org_user(self.request):
            return HttpResponseRedirect(reverse("domain-requests"))
        else:
            return HttpResponseRedirect(reverse("home"))


@grant_access(IS_DOMAIN_REQUEST_REQUESTER, HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT)
class DomainRequestDeleteView(PermissionRequiredMixin, DeleteView):
    """Delete view for home that allows the end user to delete DomainRequests"""

    object: DomainRequest  # workaround for type mismatch in DeleteView
    model = DomainRequest
    pk_url_kwarg = "domain_request_pk"

    def has_permission(self):
        """Custom override for has_permission to exclude all statuses, except WITHDRAWN and STARTED"""

        status = self.get_object().status
        valid_statuses = [DomainRequest.DomainRequestStatus.WITHDRAWN, DomainRequest.DomainRequestStatus.STARTED]
        if status not in valid_statuses:
            return False

        # Portfolio users cannot delete their requests if they aren't permissioned to do so
        if self.request.user.is_org_user(self.request):
            portfolio = self.request.session.get("portfolio")
            if not self.request.user.has_edit_request_portfolio_permission(portfolio):
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
        # the edge case where the same user may be an SO, and a requester, for example.
        if len(duplicates) > 0:
            duplicates_to_delete, _ = self._get_orphaned_contacts(domain_request, check_db=True)
            Contact.objects.filter(id__in=duplicates_to_delete).delete()

        # Return a 200 response with an empty body
        return HttpResponse(status=200)

    def _get_orphaned_contacts(self, domain_request: DomainRequest, check_db=False):
        """
        Collects all orphaned contacts associated with a given DomainRequest object.

        An orphaned contact is defined as a contact that is associated with the domain request,
        but not with any other domain_request. This includes the senior official, the requester,
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
        other_contacts = list(domain_request.other_contacts.all())
        other_contact_ids = domain_request.other_contacts.all().values_list("id", flat=True)

        # Check if the desired item still exists in the DB
        if check_db:
            so = self._get_contacts_by_id([so.id]).first() if so is not None else None
            other_contacts = self._get_contacts_by_id(other_contact_ids)

        # Pair each contact with its db related name for use in checking if it has joins
        checked_contacts = [(so, "senior_official")]
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


@grant_access(HAS_DOMAIN_REQUESTS_VIEW_ALL)
class DomainRequestStatusViewOnly(DetailView):
    """
    View-only access for domain requests both on enterprise-mode portfolios and legacy mode.

    This view provides read-only access to domain request details for users who have
    view permissions but not edit permissions.

    Access is granted via HAS_DOMAIN_REQUESTS_VIEW_ALL which handles:
    - Portfolio members with view-all domain requests permission
    - Non-portfolio users who are requesters
    - Analysts with appropriate permissions
    """

    template_name = "portfolio_domain_request_status_viewonly.html"
    model = DomainRequest
    pk_url_kwarg = "domain_request_pk"
    context_object_name = "DomainRequest"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        domain_request = self.object

        # Determine if this is a portfolio request or if user is org user
        is_portfolio = domain_request.portfolio is not None or self.request.user.is_org_user(self.request)

        if is_portfolio:
            # Create a temp wizard object to grab the step list
            wizard = PortfolioDomainRequestWizard()
            wizard.request = self.request
            context["Step"] = PortfolioDomainRequestStep.__members__
            context["steps"] = request_step_list(wizard, PortfolioDomainRequestStep)
            context["form_titles"] = wizard.titles
        else:
            # For non-portfolio requests
            wizard = DomainRequestWizard()
            wizard.request = self.request
            context["Step"] = Step.__members__
            context["steps"] = request_step_list(wizard, Step)
            context["form_titles"] = wizard.titles

        # Common context
        context["requires_feb_questions"] = domain_request.is_feb()
        context["purpose_label"] = DomainRequest.FEBPurposeChoices.get_purpose_label(domain_request.feb_purpose_choice)
        context["view_only_mode"] = True
        context["is_portfolio"] = is_portfolio
        context["portfolio"] = self.request.session.get("portfolio")

        return context


# endregion
