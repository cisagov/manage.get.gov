
from django.test import SimpleTestCase
from registrar.services.mock_cloudflare_service import MockCloudflareService


class TestMockCloudflareServiceBasics(SimpleTestCase):
    """Test the MockCloudflareService lifecycle and basic functionality"""
    mock_api_service = MockCloudflareService()

    def tearDown(self):
        if self.mock_api_service.is_active:
            self.mock_api_service.stop()

    def test_service_starts_successfully(self):
        assert not self.mock_api_service.is_active

        self.mock_api_service.start()

        assert self.mock_api_service.is_active
        assert self.mock_api_service._mock_context is not None

    def test_service_stops_successfully(self):
        self.mock_api_service.start()
        assert self.mock_api_service.is_active

        self.mock_api_service.stop()

        assert not self.mock_api_service.is_active

    def test_service_can_restart(self):
        """Test service can be stopped and restarted"""
        self.mock_api_service.start()
        self.mock_api_service.stop()
        self.mock_api_service.start()

        assert self.mock_api_service.is_active

    def test_start_when_already_active_is_safe(self):
        """Test calling start() multiple times doesn't break"""
        self.mock_api_service.start()
        self.mock_api_service.start()  # Should not error

        assert self.mock_api_service.is_active

    def test_stop_when_already_stopped_is_safe(self):
        """Test calling stop() when not active doesn't break"""
        self.mock_api_service.stop()  # Should not error
        self.mock_api_service.stop()  # Should not error

        assert not self.mock_api_service.is_active
        