"""Views for a User Profile.

"""

import logging

from django.contrib import messages
from django.views.generic.edit import FormMixin
from registrar.forms.user_profile import UserProfileForm
from django.urls import reverse
from registrar.models import (
    User,
    Contact,
)
from registrar.views.utility.permission_views import UserProfilePermissionView
from waffle.decorators import flag_is_active

logger = logging.getLogger(__name__)


class UserProfileView(UserProfilePermissionView, FormMixin):
    """
    Base View for the Domain. Handles getting and setting the domain
    in session cache on GETs. Also provides methods for getting
    and setting the domain in cache
    """

    model = Contact
    template_name = "profile.html"
    form_class = UserProfileForm

    def get(self, request, *args, **kwargs):
        logger.info("in get()")
        self.object = self.get_object()
        form = self.form_class(instance=self.object)
        context = self.get_context_data(object=self.object, form=form)
        logger.info(context)
        return self.render_to_response(context)
    
    def get_context_data(self, **kwargs):
        """Adjust context from FormMixin for formsets."""
        context = super().get_context_data(**kwargs)
        # This is a django waffle flag which toggles features based off of the "flag" table
        context["has_profile_feature_flag"] = flag_is_active(self.request, "profile_feature")
        return context
        
    def get_success_url(self):
        """Redirect to the overview page for the domain."""
        return reverse("user-profile")

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.form_class(request.POST, instance=self.object)

        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        form.save()

        messages.success(self.request, "Your profile has been updated.")

        # superclass has the redirect
        return super().form_valid(form)
                
    # Override get_object to return the logged-in user
    def get_object(self, queryset=None):
        logger.info("in get_object")
        user = self.request.user  # get the logged in user
        if hasattr(user, 'contact'):  # Check if the user has a contact instance
            logger.info(user.contact)
            return user.contact
        return None