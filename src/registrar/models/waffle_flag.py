from waffle.models import AbstractUserFlag
import logging

logger = logging.getLogger(__name__)


class WaffleFlag(AbstractUserFlag):
    """
    Custom implementation of django-waffles 'Flag' object.
    Read more here: https://waffle.readthedocs.io/en/stable/types/flag.html

    Use this class when dealing with feature flags, such as profile_feature.
    """

    class Meta:
        """Contains meta information about this class"""

        verbose_name = "waffle flag"
        verbose_name_plural = "Waffle flags"
