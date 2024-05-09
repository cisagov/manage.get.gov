"""Views for a User Profile.

"""

import logging

from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db import IntegrityError
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic.edit import FormMixin
from django.conf import settings

from registrar.models import (
    User,
)
from registrar.views.utility.permission_views import UserProfilePermissionView


logger = logging.getLogger(__name__)


class UserProfileView(UserProfilePermissionView):
    """
    Base View for the Domain. Handles getting and setting the domain
    in session cache on GETs. Also provides methods for getting
    and setting the domain in cache
    """

    template_name = "profile.html"
    
    # Override get_object to return the logged-in user
    def get_object(self, queryset=None):
        return self.request.user  # Returns the logged-in user