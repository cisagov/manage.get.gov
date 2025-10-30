from django.test import SimpleTestCase
from httpx import Client, HTTPStatusError

from registrar.services.mock_cloudflare_service import MockCloudflareService
from registrar.services.cloudflare_service import CloudflareService
from registrar.services.utility.dns_helper import make_dns_account_name


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


class TestMockCloudflareServiceEndpoints(SimpleTestCase):
    """Test that mocked endpoints return correct data"""

    mock_api_service = MockCloudflareService()

    @classmethod
    def setUpClass(cls):
        """Start mock service once for all tests in this class"""
        super().setUpClass()
        cls.mock_api_service.start()

    @classmethod
    def tearDownClass(cls):
        """Stop mock service after all tests"""
        cls.mock_api_service.stop()
        super().tearDownClass()

    def setUp(self):
        client = Client()
        self.service = CloudflareService(client)

    def test_mock_get_page_accounts_response(self):
        resp = self.service.get_page_accounts(1, 50)
        result = resp["result"]
        self.assertEqual(len(result), 3)
        self.assertEqual(result[2]["account_pubname"], make_dns_account_name("exists.gov"))

    def test_mock_get_account_zones_response(self):
        account_id = self.mock_api_service.new_account_id
        resp = self.service.get_account_zones(account_id)
        result = resp["result"]
        self.assertEqual(len(result), 2)
        for zone in result:
            self.assertNotEquals(zone.get("name"), "exists.gov")

        existing_account_id = self.mock_api_service.existing_account_id
        resp2 = self.service.get_account_zones(existing_account_id)
        result2 = resp2["result"]
        self.assertEqual(len(result2), 1)
        self.assertEquals(result2[0].get("name"), "exists.gov")

    def test_mock_create_account_response(self):
        account_name = make_dns_account_name("equity.gov")

        resp = self.service.create_account(account_name)
        result = resp["result"]

        self.assertEquals(result["name"], account_name)

    def test_mock_create_zone_response(self):
        zone_name = "peace.gov"
        account_id = "1359"

        resp = self.service.create_zone(zone_name, account_id)
        result = resp["result"]
        self.assertEquals(result["account"]["id"], account_id)
        self.assertEquals(result["name"], zone_name)

    def test_mock_create_dns_record_response(self):
        zone_id = self.mock_api_service.fake_zone_id
        record_data = {"type": "A", "name": "blog", "content": "11.22.33.44"}
        resp = self.service.create_dns_record(zone_id, record_data)
        result = resp["result"]

        self.assertEquals(result["name"], record_data["name"])
        self.assertEquals(result["type"], record_data["type"])
        self.assertEquals(result["content"], record_data["content"])

        error_403_record_data = {"type": "A", "name": "error-403-bottles", "content": "11.22.33.44"}

        with self.assertRaises(HTTPStatusError) as context:
            self.service.create_dns_record(zone_id, error_403_record_data)
        self.assertTrue("403" in str(context.exception))

        error_400_record_data = {"type": "A", "name": "error-400-bottles", "content": "11.22.33.44"}

        with self.assertRaises(HTTPStatusError) as context:
            self.service.create_dns_record(zone_id, error_400_record_data)
        self.assertTrue("400" in str(context.exception))

        error_500_record_data = {"type": "A", "name": "error-project", "content": "11.22.33.44"}

        with self.assertRaises(HTTPStatusError) as context:
            self.service.create_dns_record(zone_id, error_500_record_data)
        self.assertTrue("500" in str(context.exception))
