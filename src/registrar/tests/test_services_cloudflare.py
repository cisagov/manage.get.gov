from unittest.mock import patch, Mock, MagicMock
from django.test import TestCase

from registrar.services.cloudflare_service import CloudflareService

class TestCloudflareService(TestCase):
    """Test cases for the CloudflareService class"""
    def setUp(self):
        self.service = CloudflareService()

    @patch('registrar.services.cloudflare_service.make_api_request')
    def test_create_account_success(self, mock_make_request):
        """Test successful create_account call"""
        account_name = "test.gov test account"
        mock_make_request.return_value = {
            'success': True,
            'data': {"result": {"name": account_name, "id": "12345"}}
        }
        result = self.service.create_account(account_name)
        print(result)
        self.assertEqual(result['result']['name'], account_name)
        