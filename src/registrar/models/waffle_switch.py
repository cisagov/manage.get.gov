from waffle.models import AbstractBaseSwitch
import logging

logger = logging.getLogger(__name__)


class WaffleSwitch(AbstractBaseSwitch):
    """
    Custom implementation of django-waffles 'switch' object.
    Read more here: https://waffle.readthedocs.io/en/stable/types/switch.html
    Use this class when dealing with switches.
    """

    class Meta:
        """Contains meta information about this class"""

        verbose_name = "waffle switch"
        verbose_name_plural = "Waffle switches"
