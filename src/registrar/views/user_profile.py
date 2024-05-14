"""Views for a User Profile.

"""

import logging

from registrar.forms.user_profile import UserProfileForm
from registrar.models import (
    User,
    Contact,
)
from registrar.views.utility.permission_views import UserProfilePermissionView


logger = logging.getLogger(__name__)


class UserProfileView(UserProfilePermissionView):
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
        context = self.get_context_data(object=self.object)
        logger.info(context)
        return self.render_to_response(context)
    
    # def get_context_data(self, **kwargs):
    #     logger.info("in get_context_data")
    #     kwargs.setdefault("view", self)
    #     if self.extra_context is not None:
    #         kwargs.update(self.extra_context)
    #     return kwargs
    
    # # Override get_object to return the logged-in user
    # def get_object(self, queryset=None):
    #     logger.info("in get_object")
    #     user = self.request.user  # get the logged in user
    #     if hasattr(user, 'contact'):  # Check if the user has a contact instance
    #         logger.info(user.contact)
    #         return user.contact
    #     return None