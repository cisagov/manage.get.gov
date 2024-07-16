"""Views for a User Profile.
"""

import logging

from django.contrib import messages
from django.http import QueryDict
from django.views.generic.edit import FormMixin
from registrar.forms.user_profile import UserProfileForm, FinishSetupProfileForm
from django.urls import NoReverseMatch, reverse
from registrar.models.user import User
from registrar.models.utility.generic_helper import replace_url_queryparams
from registrar.views.utility.permission_views import UserProfilePermissionView
from waffle.decorators import waffle_flag

logger = logging.getLogger(__name__)


class UserProfileView(UserProfilePermissionView, FormMixin):
    """
    Base View for the User Profile. Handles getting and setting the User Profile
    """

    model = User
    template_name = "profile.html"
    form_class = UserProfileForm
    base_view_name = "user-profile"

    def get(self, request, *args, **kwargs):
        """Handle get requests by getting user's contact object and setting object
        and form to context before rendering."""
        self.object = self.get_object()

        # Get the redirect parameter from the query string
        redirect = request.GET.get("redirect", "home")

        form = self.form_class(instance=self.object, initial={"redirect": redirect})
        context = self.get_context_data(object=self.object, form=form, redirect=redirect)

        if (
            hasattr(self.user, "finished_setup")
            and not self.user.finished_setup
            and self.user.verification_type != User.VerificationTypeChoices.REGULAR
        ):
            context["show_confirmation_modal"] = True

        return self.render_to_response(context)

    @waffle_flag("profile_feature")  # type: ignore
    def dispatch(self, request, *args, **kwargs):  # type: ignore
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Extend get_context_data"""
        context = super().get_context_data(**kwargs)

        # Set the profile_back_button_text based on the redirect parameter
        if kwargs.get("redirect") == "domain-request:":
            context["profile_back_button_text"] = "Go back to your domain request"
        else:
            context["profile_back_button_text"] = "Go to manage your domains"

        # Show back button conditional on user having finished setup
        context["show_back_button"] = False
        if hasattr(self.user, "finished_setup") and self.user.finished_setup:
            context["user_finished_setup"] = True
            context["show_back_button"] = True

        return context

    def get_success_url(self):
        """Redirect to the user's profile page with updated query parameters."""

        # Get the redirect parameter from the form submission
        redirect_param = self.request.POST.get("redirect", None)

        # Initialize QueryDict with existing query parameters from current request
        query_params = QueryDict(mutable=True)
        query_params.update(self.request.GET)

        # Update query parameters with the 'redirect' value from form submission
        if redirect_param and redirect_param != "home":
            query_params["redirect"] = redirect_param

        # Generate the URL with updated query parameters
        base_url = reverse(self.base_view_name)

        # Generate the full url from the given query params
        full_url = replace_url_queryparams(base_url, query_params)
        return full_url

    def post(self, request, *args, **kwargs):
        """Handle post requests (form submissions)"""
        self.object = self.get_object()
        form = self.form_class(request.POST, instance=self.object)

        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_invalid(self, form):
        """If the form is invalid, conditionally display an additional error."""
        if hasattr(self.user, "finished_setup") and not self.user.finished_setup:
            messages.error(self.request, "Before you can manage your domain, we need you to add contact information.")
        form.initial["redirect"] = form.data.get("redirect")
        return super().form_invalid(form)

    def form_valid(self, form):
        """Handle successful and valid form submissions."""
        form.save()

        messages.success(self.request, "Your profile has been updated.")

        # superclass has the redirect
        return super().form_valid(form)

    def get_object(self, queryset=None):
        """Override get_object to return the logged-in user's contact"""
        self.user = self.request.user  # get the logged in user
        return self.user


class FinishProfileSetupView(UserProfileView):
    """This view forces the user into providing additional details that
    we may have missed from Login.gov"""

    template_name = "finish_profile_setup.html"
    form_class = FinishSetupProfileForm
    model = User

    base_view_name = "finish-user-profile-setup"

    def get_context_data(self, **kwargs):
        """Extend get_context_data"""
        context = super().get_context_data(**kwargs)

        # Show back button conditional on user having finished setup
        context["show_back_button"] = False
        if hasattr(self.user, "finished_setup") and self.user.finished_setup:
            if kwargs.get("redirect") == "home":
                context["show_back_button"] = True
            else:
                context["going_to_specific_page"] = True
                context["redirect_button_text"] = "Continue to your request"
        return context

    def post(self, request, *args, **kwargs):
        """Form submission posts to this view."""
        self.object = self.get_object()
        form = self.form_class(request.POST, instance=self.object)

        # Get the current form and validate it
        if form.is_valid():
            self.redirect_page = False
            if "user_setup_save_button" in request.POST:
                # Logic for when the 'Save' button is clicked, which indicates
                # user should stay on this page
                self.redirect_page = False
            elif "user_setup_submit_button" in request.POST:
                # Logic for when the other button is clicked, which indicates
                # the user should be taken to the redirect page
                self.redirect_page = True
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get_success_url(self):
        """Redirect to the redirect page, or redirect to the current page"""
        try:
            # Get the redirect parameter from the form submission
            redirect_param = self.request.POST.get("redirect", None)
            if self.redirect_page and redirect_param:
                return reverse(redirect_param)
        except NoReverseMatch as err:
            logger.error(f"get_redirect_url -> Could not find the specified page. Err: {err}")
        return super().get_success_url()
