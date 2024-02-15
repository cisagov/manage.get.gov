from django.apps import AppConfig


class RegistrarConfig(AppConfig):
    """Configure signal handling for our registrar Django application."""

    name = "registrar"

    def ready(self):
        """Runs when all Django applications have been loaded.

        We use it here to load signals that connect related models.
        """
        # noqa here because we are importing something to make the signals
        # get registered, but not using what we import
        from . import signals  # noqa
