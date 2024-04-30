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

    # Defines which waffle flags should be created at startup.
    # Add to this list if you want to add another flag that is generated at startup.
    # When you do so, you will need to add a new instance of `0091_create_waffle_flags_v{version_number}`
    # in registrar/migrations for that change to update automatically on migrate.
    DEFAULT_WAFFLE_FLAGS = [
        "profile_feature",
        "dns_hosting_feature"
    ]

    @classmethod
    def create_waffle_flags_for_migrations(cls):
        """
        Creates a pre-defined list of flags for our migrations.
        """
        logger.info("Creating default waffle flags...")
        # Flags can be changed through the command line or through django admin.
        # To keep the scope of this function minimal and simple, if we require additional
        # config on these flag, it should be done in a seperate function or as a command.
        for flag_name in cls.DEFAULT_WAFFLE_FLAGS:
            try:
                cls.objects.update_or_create(
                    name=flag_name,
                    # Booleans like superusers or is_staff can be set here, if needed.
                    defaults={
                        'note': 'Auto-generated waffle flag'
                    }
                )
            except Exception as e:
                logger.error(f"An error occurred when attempting to add or update flag {flag_name}: {e}")
    
    @classmethod
    def delete_waffle_flags_for_migrations(cls):
        """
        Delete a pre-defined list of flags for our migrations (the reverse_code operation).
        """
        logger.info("Deleting default waffle flags...")
        existing_flags = cls.objects.filter(name__in=cls.DEFAULT_WAFFLE_FLAGS)
        for flag in existing_flags:
            try:
                cls.objects.get(name=flag.name).delete()
            except Exception as e:
                logger.error(f"An error occurred when attempting to delete flag {flag.name}: {e}")