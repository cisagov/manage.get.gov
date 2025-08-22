from unittest.mock import patch
from django.test import SimpleTestCase

from registrar.services.cloudflare_service import CloudflareService
from registrar.services.dns_host_service import DnsHostService
from registrar.utility.errors import APIError

class TestDnsHostService(SimpleTestCase):
    
    def setUp(self):
        self.service = DnsHostService()

    @patch('registrar.services.dns_host_service.CloudflareService.create_zone')
    @patch('registrar.services.dns_host_service.CloudflareService.create_account')
    def test_dns_setup_success(self, mock_create_account, mock_create_zone):
        account_name = "Account for test.gov"
        account_id = "12345"
        mock_create_account.return_value = {
            "result": {"id": account_id }
        }
        
        zone_id = "9876"
        mock_create_zone.return_value = {
            "result": {"id": zone_id}
        }
        
        returned_account_id, returned_zone_id = self.service.dns_setup(account_name)
        self.assertEqual(returned_account_id, account_id)
        self.assertEqual(returned_zone_id, zone_id)

    @patch('registrar.services.dns_host_service.CloudflareService.create_zone')
    @patch('registrar.services.dns_host_service.CloudflareService.create_account')
    def test_dns_setup_failure(self, mock_create_account, mock_create_zone):
        account_name = " "
        mock_create_account.side_effect = APIError(
            'DNS setup failed to create account'
        )
    
        with self.assertRaises(APIError) as context:
            self.service.dns_setup(account_name)
        
        mock_create_account.assert_called_once_with(account_name)
        self.assertEqual(context.exception, APIError('DNS setup failed to create account'))

    @patch('registrar.services.dns_host_service.CloudflareService.create_dns_record')
    def test_create_record_success(self, mock_create_dns_record):
    
        zone_id = '1234'
        record_data = {
            "type": "A",
            "name": "test.gov", # record name
            "content": "1.1.1.1", # IPv4
            "ttl": 1,
            "comment": "Test record"
        }

        mock_create_dns_record.return_value = {
            "result": {"id": zone_id, 
            **record_data
            }
        }

        response = self.service.create_record(zone_id, record_data)
        self.assertEqual(response["result"]["id"], zone_id)
        self.assertEqual(response["result"]["name"], "test.gov")

    @patch('registrar.services.dns_host_service.CloudflareService.create_dns_record')
    def test_create_record_failure(self, mock_create_dns_record):
    
        zone_id = '1234'
        record_data = {
            "type": "A",
            "content": "1.1.1.1", # IPv4
            "ttl": 1,
            "comment": "Test record"
        }

        mock_create_dns_record.side_effect = APIError("Bad request: missing name")

        with self.assertRaises(APIError) as context:
            self.service.create_record(zone_id, record_data)
        
        self.assertEqual(context.exception, APIError("Bad request: missing name"))

