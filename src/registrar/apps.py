from django.apps import AppConfig

class RegistrarConfig(AppConfig):
    """Configure signal handling for our registrar Django application."""

    name = "registrar"

    def ready(self):
        import registrar.signals  # noqa

        from registrar.services.mock_cloudflare_service import MockCloudflareService
        mock_cloudflare_service = MockCloudflareService()
        mock_cloudflare_service.start()
