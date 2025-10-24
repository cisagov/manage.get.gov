from django.apps import AppConfig
from django.conf import settings


class RegistrarConfig(AppConfig):
    """Configure signal handling for our registrar Django application."""

    name = "registrar"

    def ready(self):
        import registrar.signals  # noqa

        if settings.DNS_MOCK_EXTERNAL_APIS:
            from registrar.services.mock_cloudflare_service import MockCloudflareService

            mock_cloudflare_service = MockCloudflareService()
            mock_cloudflare_service.start()
