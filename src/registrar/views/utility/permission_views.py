"""View classes that enforce authorization."""

import abc  # abstract base class

from django.views.generic import DetailView
from registrar.models import Portfolio
from registrar.models.user import User

from .mixins import (
    UserProfilePermission,
)
import logging

logger = logging.getLogger(__name__)


class UserProfilePermissionView(UserProfilePermission, DetailView, abc.ABC):
    """Abstract base view for user profile view that enforces permissions.

    This abstract view cannot be instantiated. Actual views must specify
    `template_name`.
    """

    # DetailView property for what model this is viewing
    model = User
    # variable name in template context for the model object
    context_object_name = "user"

    # Abstract property enforces NotImplementedError on an attribute.
    @property
    @abc.abstractmethod
    def template_name(self):
        raise NotImplementedError
