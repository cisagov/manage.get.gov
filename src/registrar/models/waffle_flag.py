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

    @staticmethod
    def get_default_waffle_flags():
        """
        Defines which waffle flags should be created at startup.

        Add to this function if you want to add another flag that is generated at startup.
        When you do so, you will need to add a new instance of `0091_create_waffle_flags_v{version_number}`
        in registrar/migrations for that change to update automatically on migrate.
        """
        default_flags = [
            # flag_name, flag_note
            ("profile_feature", "Used for profiles"),
            ("dns_hosting_feature", "Used for dns hosting"),
        ]
        return default_flags

    @staticmethod
    def create_waffle_flags_for_migrations(apps, default_waffle_flags):
        """
        Creates a list of flags for our migrations.
        """
        logger.info("Creating default waffle flags...")
        WaffleFlag = apps.get_model("registrar", "WaffleFlag")
        # Flags can be changed through the command line or through django admin.
        # To keep the scope of this function minimal and simple, if we require additional
        # config on these flag, it should be done in a seperate function or as a command.
        for flag_name, flag_note in default_waffle_flags:
            try:
                WaffleFlag.objects.update_or_create(
                    name=flag_name,
                    # Booleans like superusers or is_staff can be set here, if needed.
                    defaults={"note": flag_note},
                )
            except Exception as e:
                logger.error(f"An error occurred when attempting to add or update flag {flag_name}: {e}")

    @staticmethod
    def delete_waffle_flags_for_migrations(apps, default_waffle_flags):
        """
        Delete a list of flags for our migrations (the reverse_code operation).
        """
        logger.info("Deleting default waffle flags...")
        WaffleFlag = apps.get_model("registrar", "WaffleFlag")
        existing_flags = WaffleFlag.objects.filter(name__in=default_waffle_flags)
        for flag in existing_flags:
            try:
                WaffleFlag.objects.get(name=flag.name).delete()
            except Exception as e:
                logger.error(f"An error occurred when attempting to delete flag {flag.name}: {e}")
