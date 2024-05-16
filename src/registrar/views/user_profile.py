"""Views for a User Profile.

"""

import logging

from django.contrib import messages
from django.views.generic.edit import FormMixin
from registrar.forms.user_profile import UserProfileForm
from django.urls import reverse
from registrar.models import (
    Contact,
)
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
        self.object = self.get_object()
        form = self.form_class(instance=self.object)
        context = self.get_context_data(object=self.object, form=form)
        return self.render_to_response(context)

    @waffle_flag("profile_feature")
    def dispatch(self, request, *args, **kwargs):
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
        self.object = self.get_object()
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
