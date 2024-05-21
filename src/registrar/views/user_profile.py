"""Views for a User Profile.

"""

from enum import Enum
import logging
from urllib.parse import quote

from django.contrib import messages
from django.views.generic.edit import FormMixin
from registrar.forms.user_profile import UserProfileForm, FinishSetupProfileForm
from django.urls import NoReverseMatch, reverse
from registrar.models import (
    Contact,
)
from registrar.views.utility.permission_views import UserProfilePermissionView
from waffle.decorators import flag_is_active, waffle_flag

from registrar.templatetags.url_helpers import public_site_url
from registrar.models.utility.generic_helper import replace_url_queryparams
from django.utils.safestring import mark_safe
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect

logger = logging.getLogger(__name__)


class UserProfileView(UserProfilePermissionView, FormMixin):
    """
    Base View for the User Profile. Handles getting and setting the User Profile
    """

    model = Contact
    template_name = "profile.html"
    form_class = UserProfileForm

    def get(self, request, *args, **kwargs):
        """Handle get requests by getting user's contact object and setting object
        and form to context before rendering."""
        self._refresh_session_and_object(request)
        form = self.form_class(instance=self.object)
        context = self.get_context_data(object=self.object, form=form)
        return self.render_to_response(context)

    def _refresh_session_and_object(self, request):
        """Sets the current session to self.session and the current object to self.object"""
        self.session = request.session
        self.object = self.get_object()

    @waffle_flag("profile_feature")  # type: ignore
    def dispatch(self, request, *args, **kwargs):  # type: ignore
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Extend get_context_data to include has_profile_feature_flag"""
        context = super().get_context_data(**kwargs)
        # This is a django waffle flag which toggles features based off of the "flag" table
        context["has_profile_feature_flag"] = flag_is_active(self.request, "profile_feature")
        return context

    def get_success_url(self):
        """Redirect to the user's profile page."""
        return reverse("user-profile")

    def post(self, request, *args, **kwargs):
        """Handle post requests (form submissions)"""
        self._refresh_session_and_object(request)
        form = self.form_class(request.POST, instance=self.object)

        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        """Handle successful and valid form submissions."""
        form.save()

        messages.success(self.request, "Your profile has been updated.")

        # superclass has the redirect
        return super().form_valid(form)

    def get_object(self, queryset=None):
        """Override get_object to return the logged-in user's contact"""
        user = self.request.user  # get the logged in user
        if hasattr(user, "contact"):  # Check if the user has a contact instance
            return user.contact
        return None


class FinishProfileSetupView(UserProfileView):
    """This view forces the user into providing additional details that
    we may have missed from Login.gov"""

    template_name = "finish_profile_setup.html"
    form_class = FinishSetupProfileForm
    model = Contact

    redirect_type = None

    class RedirectType(Enum):
        """
        Enums for each type of redirection. Enforces behaviour on `get_redirect_url()`.

        - HOME: We want to redirect to reverse("home")
        - BACK_TO_SELF: We want to redirect back to reverse("finish-user-profile-setup")
        - TO_SPECIFIC_PAGE: We want to redirect to the page specified in the queryparam "redirect"
        - COMPLETE_SETUP: Indicates that we want to navigate BACK_TO_SELF, but the subsequent
        redirect after the next POST should be either HOME or TO_SPECIFIC_PAGE
        """

        HOME = "home"
        BACK_TO_SELF = "back_to_self"
        COMPLETE_SETUP = "complete_setup"
        TO_SPECIFIC_PAGE = "domain_request"

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)
        context["email_sublabel_text"] = self._email_sublabel_text()

        if self.redirect_type == self.RedirectType.COMPLETE_SETUP:
            context["confirm_changes"] = True

        if "redirect_viewname" in self.session:
            context["going_to_specific_page"] = True
            context["redirect_button_text"] = "Continue to your request"

        return context

    def _email_sublabel_text(self):
        """Returns the lengthy sublabel for the email field"""
        help_url = public_site_url("help/account-management/#get-help-with-login.gov")
        return mark_safe(
            "We recommend using your work email for your .gov account. "
            "If the wrong email is displayed below, you’ll need to update your Login.gov account "
            f'and log back in. <a class="usa-link" href={help_url}>Get help with your Login.gov account.</a>'
        )  # nosec

    def get_success_message(self, cleaned_data):
        """Content of the returned success message"""
        return "Your profile has been successfully updated."

    @method_decorator(csrf_protect)
    def dispatch(self, request, *args, **kwargs):
        """
        Handles dispatching of the view, applying CSRF protection and checking the 'profile_feature' flag.

        This method sets the redirect type based on the 'redirect' query parameter,
        defaulting to BACK_TO_SELF if not provided.
        It updates the session with the redirect view name if the redirect type is TO_SPECIFIC_PAGE.

        Returns:
            HttpResponse: The response generated by the parent class's dispatch method.
        """

        # Update redirect type based on the query parameter if present
        redirect_type = request.GET.get("redirect", self.RedirectType.BACK_TO_SELF.value)

        all_redirect_types = [r.value for r in self.RedirectType]
        if redirect_type in all_redirect_types:
            self.redirect_type = self.RedirectType(redirect_type)
        else:
            # If the redirect type is undefined, then we assume that
            # we are specifying a particular page to redirect to.
            self.redirect_type = self.RedirectType.TO_SPECIFIC_PAGE

            # Store the page that we want to redirect to for later use
            request.session["redirect_viewname"] = str(redirect_type)

        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Form submission posts to this view."""
        self._refresh_session_and_object(request)
        form = self.form_class(request.POST, instance=self.object)

        # Get the current form and validate it
        if form.is_valid():
            if "contact_setup_save_button" in request.POST:
                # Logic for when the 'Save' button is clicked
                self.redirect_type = self.RedirectType.COMPLETE_SETUP
            elif "contact_setup_submit_button" in request.POST:
                if "redirect_viewname" in self.session:
                    self.redirect_type = self.RedirectType.TO_SPECIFIC_PAGE
                else:
                    self.redirect_type = self.RedirectType.HOME

            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get_success_url(self):
        """Redirect to the nameservers page for the domain."""
        redirect_url = self.get_redirect_url()
        return redirect_url

    def get_redirect_url(self):
        """
        Returns a URL string based on the current value of self.redirect_type.

        Depending on self.redirect_type, constructs a base URL and appends a
        'redirect' query parameter. Handles different redirection types such as
        HOME, BACK_TO_SELF, COMPLETE_SETUP, and TO_SPECIFIC_PAGE.

        Returns:
            str: The full URL with the appropriate query parameters.
        """

        # These redirect types redirect to the same page
        self_redirect = [self.RedirectType.BACK_TO_SELF, self.RedirectType.COMPLETE_SETUP]

        # Maps the redirect type to a URL
        base_url = ""
        try:
            if self.redirect_type in self_redirect:
                base_url = reverse("finish-user-profile-setup", kwargs={"pk": self.object.pk})
            elif self.redirect_type == self.RedirectType.TO_SPECIFIC_PAGE:
                # We only allow this session value to use viewnames,
                # because this restricts what can be redirected to.
                desired_view = self.session["redirect_viewname"]
                self.session.pop("redirect_viewname")
                base_url = reverse(desired_view)
            else:
                base_url = reverse("home")
        except NoReverseMatch as err:
            logger.error(f"get_redirect_url -> Could not find the specified page. Err: {err}")

        query_params = {}

        # Quote cleans up the value so that it can be used in a url
        query_params["redirect"] = quote(self.redirect_type.value)

        # Generate the full url from the given query params
        full_url = replace_url_queryparams(base_url, query_params)
        return full_url
