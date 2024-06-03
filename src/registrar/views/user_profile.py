"""Views for a User Profile.

"""

import logging
from urllib.parse import parse_qs, unquote

from django.contrib import messages
from django.views.generic.edit import FormMixin
from registrar.forms.user_profile import UserProfileForm
from django.urls import reverse
from registrar.models import (
    Contact,
)
from registrar.models.utility.generic_helper import replace_url_queryparams
from registrar.views.utility.permission_views import UserProfilePermissionView
from waffle.decorators import flag_is_active, waffle_flag


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

        return_to_request = request.GET.get("return_to_request")
        if return_to_request:
            context["return_to_request"] = True

        return self.render_to_response(context)

    def _refresh_session_and_object(self, request):
        """Sets the current session to self.session and the current object to self.object"""
        self.session = request.session
        self.object = self.get_object()

    @waffle_flag("profile_feature")  # type: ignore
    def dispatch(self, request, *args, **kwargs):  # type: ignore
        # Store the original queryparams to persist them
        query_params = request.META["QUERY_STRING"]
        request.session["query_params"] = query_params
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Extend get_context_data to include has_profile_feature_flag"""
        context = super().get_context_data(**kwargs)
        # This is a django waffle flag which toggles features based off of the "flag" table
        context["has_profile_feature_flag"] = flag_is_active(self.request, "profile_feature")
        return context

    def get_success_url(self):
        """Redirect to the user's profile page."""

        query_params = {}
        if "query_params" in self.session:
            params = unquote(self.session["query_params"])
            query_params = parse_qs(params)

        # Preserve queryparams and add them back to the url
        base_url = reverse("user-profile")
        new_redirect = replace_url_queryparams(base_url, query_params, convert_list_to_csv=True)
        return new_redirect

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
