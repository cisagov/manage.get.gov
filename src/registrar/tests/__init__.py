from django.dispatch import receiver
from django.test.signals import setting_changed


@receiver(setting_changed)
def _sync_dns_mock(sender, setting, value, **kwargs):
    """This ensures that when a setting is changed (ex. override_settings), if we are mocking Cloudflare apis,
    we start the mock, and if it's active and we are not mocking CF apis, it stops the mock
    """
    if setting != "DNS_MOCK_EXTERNAL_APIS":
        return
    from registrar.services.mock_cloudflare_service import MockCloudflareService

    mock = MockCloudflareService()
    if value and not mock.is_active:
        mock.start()
    elif not value and mock.is_active:
        mock.stop()
