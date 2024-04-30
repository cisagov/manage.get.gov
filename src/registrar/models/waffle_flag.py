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

    @classmethod
    def create_waffle_flags(cls):
        """
        Creates a pre-defined list of flags for our migrations.
        """
        logger.info("Creating default waffle flags...")
        try:
            # Flags can be activated through the command line or through django admin.
            # To keep the scope of this function minimal and simple, if we require additional
            # config on these flag, it should be done in a seperate function or as a command.
            flag_names = [
                "profile_feature",
                "dns_hosting_feature",
            ]
            flags = [cls(name=flag_name) for flag_name in flag_names]
            cls.objects.bulk_create(flags)
        except Exception as e:
            logger.error(f"An error occurred when attempting to create WaffleFlags: {e}")