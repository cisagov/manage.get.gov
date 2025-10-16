from django.apps import AppConfig


class RegistrarConfig(AppConfig):
    """Configure signal handling for our registrar Django application."""

    name = "registrar"

    def ready(self):
        import registrar.signals  # noqa

        from . import checks  # noqa: F401  # imported to register system checks, flake8 can ignore 'unused import'
