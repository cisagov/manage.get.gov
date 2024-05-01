from waffle.models import AbstractBaseSample
import logging

logger = logging.getLogger(__name__)


class WaffleSample(AbstractBaseSample):
    """
    Custom implementation of django-waffles 'sample' object.
    Read more here: https://waffle.readthedocs.io/en/stable/types/sample.html

    Use this class when dealing with samples.
    """

    class Meta:
        """Contains meta information about this class"""

        verbose_name = "waffle sample"
        verbose_name_plural = "Waffle samples"
