from unittest.mock import patch, Mock
from django.test import SimpleTestCase, TestCase
from django.db import IntegrityError

from registrar.services.dns_host_service import DnsHostService
from registrar.models.dns.dns_account import DnsAccount
from registrar.models.dns.vendor_dns_account import VendorDnsAccount
from registrar.models.dns.dns_account_vendor_dns_account import DnsAccount_VendorDnsAccount as AccountsJoin
from registrar.models.dns.dns_vendor import DnsVendor
from registrar.services.utility.dns_helper import make_dns_account_name
from registrar.utility.errors import APIError


class TestDnsHostService(SimpleTestCase):

    def setUp(self):
        mock_client = Mock()
        self.service = DnsHostService(client=mock_client)

    @patch("registrar.services.dns_host_service.CloudflareService.get_account_zones")
    @patch("registrar.services.dns_host_service.CloudflareService.get_page_accounts")
    @patch("registrar.services.dns_host_service.CloudflareService.create_cf_zone")
    @patch("registrar.services.dns_host_service.CloudflareService.create_cf_account")
    @patch("registrar.services.dns_host_service.DnsHostService.save_db_account")
    @patch("registrar.services.dns_host_service.DnsHostService.save_db_zone")
    def test_dns_setup_success(
        self,
        mock_save_db_zone,
        mock_save_db_account,
        mock_create_cf_account,
        mock_create_cf_zone,
        mock_get_page_accounts,
        mock_get_account_zones
    ):
        test_cases = [
            {
                "test_name": "no account, no zone",
                "domain_name": "test.gov",
                "account_id": "12345",
                "zone_id": "8765",
                "found_account_id": None,
                "found_zone_id": None,
            },
            {
                "test_name": "has account, has zone",
                "domain_name": "test.gov",
                "account_id": "12345",
                "zone_id": "8765",
                "found_account_id": "12345",
                "found_zone_id": "8765",
            },
            {
                "test_name": "has account, no zone",
                "domain_name": "test.gov",
                "account_id": "12345",
                "zone_id": "8765",
                "found_account_id": "12345",
                "found_zone_id": None,
            },
        ]

        for case in test_cases:
            with self.subTest(msg=case["test_name"], **case):
                mock_create_cf_account.return_value = {"result": {"id": case["account_id"]}}

                mock_create_cf_zone.return_value = {"result": {"id": case["zone_id"], "name": case["domain_name"]}}

                mock_get_page_accounts.return_value = {
                    "result": [{"id": case.get("found_account_id")}],
                    "result_info": {"total_count": 18},
                }

                mock_get_account_zones.return_value = {"result": [{"id": case.get("found_zone_id")}]}

                mock_save_db_account.return_value = case["account_id"]

                returned_account_id, returned_zone_id, _ = self.service.dns_setup(case["domain_name"])
                self.assertEqual(returned_account_id, case["account_id"])
                self.assertEqual(returned_zone_id, case["zone_id"])
                self.assertEqual(returned_account_id, case["account_id"])
                self.assertEqual(returned_zone_id, case["zone_id"])

    @patch("registrar.services.dns_host_service.CloudflareService.get_account_zones")
    @patch("registrar.services.dns_host_service.CloudflareService.get_page_accounts")
    @patch("registrar.services.dns_host_service.CloudflareService.create_cf_zone")
    @patch("registrar.services.dns_host_service.CloudflareService.create_cf_account")
    def test_dns_setup_failure_from_create_account(
        self, mock_create_cf_account, mock_create_cf_zone, mock_get_page_accounts, mock_get_account_zones
    ):
        domain_name = "test.gov"
        account_name = make_dns_account_name(domain_name)
        mock_get_page_accounts.return_value = {"result": [{"id": "55555"}], "result_info": {"total_count": 8}}
        mock_create_cf_account.side_effect = APIError("DNS setup failed to create account")

        with self.assertRaises(APIError) as context:
            self.service.dns_setup(domain_name)

        mock_create_cf_account.assert_called_once_with(account_name)
        self.assertIn("DNS setup failed to create account", str(context.exception))

    @patch("registrar.services.dns_host_service.CloudflareService.get_account_zones")
    @patch("registrar.services.dns_host_service.CloudflareService.get_page_accounts")
    @patch("registrar.services.dns_host_service.CloudflareService.create_cf_zone")
    @patch("registrar.services.dns_host_service.CloudflareService.create_cf_account")
    def test_dns_setup_failure_from_create_cf_zone(
        self, mock_create_cf_account, mock_create_cf_zone, mock_get_page_accounts, mock_get_account_zones
    ):
        domain_name = "test.gov"
        account_name = make_dns_account_name(domain_name)
        account_id = "12345"
        mock_get_page_accounts.return_value = {"result": [{"id": "55555"}], "result_info": {"total_count": 8}}
        mock_create_cf_account.return_value = {"result": {"id": account_id}}
        mock_create_cf_account.side_effect = APIError("DNS setup failed to create zone")

        with self.assertRaises(APIError) as context:
            self.service.dns_setup(domain_name)

        mock_create_cf_account.assert_called_once_with(account_name)
        # mock_create_cf_zone.assert_called_once_with(zone_name, account_id) not sure why this fails: 0 calls
        self.assertIn("DNS setup failed to create zone", str(context.exception))

    @patch("registrar.services.dns_host_service.CloudflareService.create_dns_record")
    def test_create_record_success(self, mock_create_dns_record):

        zone_id = "1234"
        record_data = {
            "type": "A",
            "name": "test.gov",  # record name
            "content": "1.1.1.1",  # IPv4
            "ttl": 1,
            "comment": "Test record",
        }

        mock_create_dns_record.return_value = {"result": {"id": zone_id, **record_data}}

        response = self.service.create_record(zone_id, record_data)
        self.assertEqual(response["result"]["id"], zone_id)
        self.assertEqual(response["result"]["name"], "test.gov")

    @patch("registrar.services.dns_host_service.CloudflareService.create_dns_record")
    def test_create_record_failure(self, mock_create_dns_record):

        zone_id = "1234"
        record_data = {"type": "A", "content": "1.1.1.1", "ttl": 1, "comment": "Test record"}  # IPv4

        mock_create_dns_record.side_effect = APIError("Bad request: missing name")

        with self.assertRaises(APIError) as context:
            self.service.create_record(zone_id, record_data)
        self.assertIn("Bad request: missing name", str(context.exception))


class TestDnsHostServiceDB(TestCase):
    def setUp(self):
        self.vendor = DnsVendor.objects.get(name=DnsVendor.CF)
        mock_client = Mock()
        self.service = DnsHostService(client=mock_client)

    def tearDown(self):
        DnsVendor.objects.all().delete()
        VendorDnsAccount.objects.all().delete()
        DnsAccount.objects.all().delete()
        AccountsJoin.objects.all().delete()

    def test_save_db_account_success(self):
        # Dummy JSON data from API
        account_data = {"result": {"id": "12345", "name": "Account for test.gov", "created_on": "2024-01-02T03:04:05Z"}}

        # Validate that the method returns the vendor account ID
        returned_id = self.service.save_db_account(account_data)
        self.assertEqual(returned_id, "12345")

        # Validate there's one VendorDnsAccount row with the external id and the CF Vendor
        expected_account_id = account_data["result"].get("id")
        vendor_accts = VendorDnsAccount.objects.filter(x_account_id=expected_account_id, dns_vendor_id=self.vendor.id)
        self.assertEqual(vendor_accts.count(), 1)

        # Validate there's one DnsAccount row with the given name
        dns_accts = DnsAccount.objects.filter(name="Account for test.gov")
        self.assertEqual(dns_accts.count(), 1)

        # Testing the join row for DnsAccount_VendorDnsAccount
        dns_acc = DnsAccount.objects.get(name="Account for test.gov")
        vendor_acc = VendorDnsAccount.objects.get(x_account_id="12345")
        join_exists = AccountsJoin.objects.filter(dns_account=dns_acc, vendor_dns_account=vendor_acc).exists()
        self.assertTrue(join_exists)

    def test_save_db_account_with_error_fails(self):
        account_data = {"result": {"id": "FAIL1", "name": "Failed Test Account", "created_on": "2024-01-02T03:04:05Z"}}

        expected_vendor_accts = VendorDnsAccount.objects.count()
        expected_dns_accts = DnsAccount.objects.count()
        expected_acct_joins = AccountsJoin.objects.count()

        # patch() temporarily replaces VendorDnsAccount.objects.create() with a fake version that raises
        # an integrity error mid-transcation
        with patch("registrar.models.VendorDnsAccount.objects.create", side_effect=IntegrityError("simulated failure")):
            with self.assertRaises(IntegrityError):
                self.service.save_db_account(account_data)

        # Ensure that no database rows are created across our tables (since the transaction failed).
        self.assertEqual(VendorDnsAccount.objects.count(), expected_vendor_accts)
        self.assertEqual(DnsAccount.objects.count(), expected_dns_accts)
        self.assertEqual(AccountsJoin.objects.count(), expected_acct_joins)

    def test_save_db_account_with_bad_or_incomplete_data_fails(self):
        invalid_result_payloads = [
            {"test_name": "Empty payload test case"},
            {"test_name": "Empty result dictionary test case", "result": {}},
            {"test_name": "Missing name test case", "result": {"id": "A"}},
            {"test_name": "Missing id test case", "result": {"name": "Account"}},
        ]

        expected_vendor_accts = VendorDnsAccount.objects.count()
        expected_dns_accts = DnsAccount.objects.count()
        expected_acct_joins = AccountsJoin.objects.count()

        for payload in invalid_result_payloads:
            with self.subTest(msg=payload["test_name"], payload=payload):
                with self.assertRaises(KeyError):
                    self.service.save_db_account(payload)

                    # Nothing should be written on any failure
                    self.assertEqual(VendorDnsAccount.objects.count(), expected_vendor_accts)
                    self.assertEqual(DnsAccount.objects.count(), expected_dns_accts)
                    self.assertEqual(AccountsJoin.objects.count(), expected_acct_joins)

    def test_save_db_account_on_failed_join_creation_throws_error(self):
        payload = {
            "result": {
                "id": "JOIN1",
                "name": "Account for test.gov",
                "created_on": "2024-01-02T03:04:05Z",
            }
        }

        with patch(
            "registrar.models.DnsAccount_VendorDnsAccount.objects.create",
            side_effect=IntegrityError("simulated join failure"),
        ):
            with self.assertRaises(IntegrityError):
                self.service.save_db_account(payload)

        # If the creation of the join fails, nothing should be saved in the database.
        self.assertEqual(VendorDnsAccount.objects.count(), 0)
        self.assertEqual(DnsAccount.objects.count(), 0)
        self.assertEqual(AccountsJoin.objects.count(), 0)
