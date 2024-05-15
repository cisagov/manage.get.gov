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

    # def get(self, request, *args, **kwargs):
    #     logger.info("in get")
    #     return super().get(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        logger.info("in get()")
        self.object = self.get_object()
        form = self.form_class(instance=self.object)
        context = self.get_context_data(object=self.object, form=form)
        logger.info(context)
        return self.render_to_response(context)
    
    def get_success_url(self):
        """Redirect to the overview page for the domain."""
        return reverse("user-profile")

    # def post(self, request, *args, **kwargs):
    #     # Handle POST request logic here
    #     form = self.get_form()
    #     if form.is_valid():
    #         # Save form data or perform other actions
    #         return HttpResponseRedirect(reverse('profile_success'))  # Redirect to a success page
    #     else:
    #         # Form is not valid, re-render the page with errors
    #         return self.render_to_response(self.get_context_data(form=form))

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        form.instance.id = self.object.id
        form.instance.created_at = self.object.created_at
        form.instance.user = self.request.user
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