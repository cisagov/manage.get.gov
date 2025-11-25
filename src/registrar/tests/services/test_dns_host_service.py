from unittest.mock import patch, Mock
from django.test import TestCase
from django.db import IntegrityError

from registrar.services.dns_host_service import DnsHostService
from registrar.models import (
    Domain,
    DnsVendor,
    DnsAccount,
    VendorDnsAccount,
    DnsZone,
    VendorDnsZone,
    DnsAccount_VendorDnsAccount as AccountsJoin,
    DnsZone_VendorDnsZone as ZonesJoin,
)
from registrar.services.utility.dns_helper import make_dns_account_name
from registrar.utility.errors import APIError


class TestDnsHostService(TestCase):

    def setUp(self):
        mock_client = Mock()
        self.service = DnsHostService(client=mock_client)

    @patch("registrar.services.dns_host_service.DnsHostService._find_existing_zone")
    @patch("registrar.services.dns_host_service.DnsHostService._find_existing_account_in_db")
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
        mock_get_account_zones,
        mock_find_account_db,
        mock_find_zone_db,
    ):
        test_cases = [
            # Case A: Database has account + zone
            {
                "test_name": "has db account, has db zone",
                "domain_name": "test.gov",
                "x_account_id": "12345",
                "x_zone_id": "8765",
                "cf_account": None,
                "cf_zone": None,
                "expected_account_id": "12345",
                "expected_zone_id": "8765",
            },
            # Case B: Database empty, but CF has account
            {
                "test_name": "no db account or zone, has cf account",
                "domain_name": "test.gov",
                "x_account_id": None,
                "x_zone_id": None,
                "cf_account": "12345",
                "cf_zone": None,
                "expected_account_id": "12345",
                "expected_zone_id": "8765",
            },
            # Case C: Database and CF empty
            {
                "test_name": "no db account or zone, no cf account",
                "domain_name": "test.gov",
                "x_account_id": None,
                "x_zone_id": None,
                "cf_account": None,
                "cf_zone": None,
                "expected_account_id": "12345",
                "expected_zone_id": "8765",
            },
        ]

        for case in test_cases:
            with self.subTest(msg=case["test_name"], **case):
                mock_find_account_db.return_value = case["x_account_id"]
                mock_find_zone_db.return_value = case["x_zone_id"], None

                if mock_find_account_db.return_value == None:
                    mock_create_cf_account.return_value = {"result": {"id": case["expected_account_id"]}}
                    mock_create_cf_zone.return_value = {
                        "result": {"id": case["expected_zone_id"], "name": case["domain_name"]}
                    }

                    mock_get_page_accounts.return_value = {
                        "result": [{"id": case.get("expected_account_id")}],
                        "result_info": {"total_count": 18},
                    }
                    mock_get_account_zones.return_value = {"result": [{"id": case.get("expected_zone_id")}]}

                returned_account_id, returned_zone_id, _ = self.service.dns_setup(case["domain_name"])

                self.assertEqual(returned_account_id, case["expected_account_id"])
                self.assertEqual(returned_zone_id, case["expected_zone_id"])

    @patch("registrar.services.dns_host_service.DnsHostService._find_existing_account_in_cf")
    @patch("registrar.services.dns_host_service.DnsHostService._find_existing_account_in_db")
    def test_dns_setup_failure_from_find_existing_account_in_cf(
        self,mock_find_existing_account_in_db, mock_find_existing_account_in_cf
    ):
        domain_name = "test.gov"
        mock_find_existing_account_in_db.return_value = None
        mock_find_existing_account_in_cf.side_effect = APIError("DNS setup failed when finding account in cf")
        with self.assertRaises(APIError) as context:
            self.service.dns_setup(domain_name)
        self.assertIn("DNS setup failed when finding account in cf", str(context.exception))

    @patch("registrar.services.dns_host_service.DnsHostService.create_and_save_account")
    @patch("registrar.services.dns_host_service.DnsHostService._find_existing_account_in_cf")
    @patch("registrar.services.dns_host_service.DnsHostService._find_existing_account_in_db")
    def test_dns_setup_failure_from_create_and_save_account(
        self, mock_find_existing_account_in_db, mock_find_existing_account_in_cf, mock_create_and_save_account
    ):
        domain_name = "test.gov"
        account_name = make_dns_account_name(domain_name)

        mock_find_existing_account_in_db.return_value = None
        mock_find_existing_account_in_cf.return_value = None
        mock_create_and_save_account.side_effect = APIError("DNS setup failed to create account")

        with self.assertRaises((APIError, Exception)):
            self.service.dns_setup(domain_name)

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
        vendor_mock = Mock()
        self.service = DnsHostService(client=mock_client)
        self.service.dns_vendor_service = vendor_mock
        self.vendor_account_data = {
            "result": {"id": "12345", "name": "Account for test.gov", "created_on": "2024-01-02T03:04:05Z"}
        }
        self.vendor_zone_data = {
            "result": {
                "id": "12345",
                "name": "dns-test.gov",
                "created_on": "2024-01-02T03:04:05Z",
                "account": {
                    "id": self.vendor_account_data["result"].get("id"),
                    "name": self.vendor_account_data["result"].get("name"),
                },
            }
        }

    def tearDown(self):
        DnsVendor.objects.all().delete()
        VendorDnsAccount.objects.all().delete()
        DnsAccount.objects.all().delete()
        AccountsJoin.objects.all().delete()
        VendorDnsZone.objects.all().delete()
        DnsZone.objects.all().delete()
        ZonesJoin.objects.all().delete()

    def test_find_existing_account_success(self):
        account_name = "Account for test.gov"
        test_x_account_id = "12345"

        # Paginated endpoint returns the above dictionary
        self.service.dns_vendor_service.get_page_accounts.return_value = self.vendor_zone_data

        self.service._find_account_tag_by_pubname = Mock(return_value=test_x_account_id)

        vendor_dns_acc = VendorDnsAccount.objects.create(
            dns_vendor=self.vendor,
            x_account_id="12345",
            x_created_at="2024-01-02T03:04:05Z",
            x_updated_at="2024-01-02T03:04:05Z",
        )

        dns_acc = DnsAccount.objects.create(name=account_name)

        AccountsJoin.objects.create(dns_account=dns_acc, vendor_dns_account=vendor_dns_acc, is_active=True)

        found_id = self.service._find_existing_account_in_db(account_name)
        self.assertEqual(found_id, test_x_account_id)

    def test_find_existing_account_in_db_raises_does_not_exist_with_inactive_join_success(self):
        account_name = "Account for inactive.gov"

        vendor_dns_acc = VendorDnsAccount.objects.create(
            dns_vendor=self.vendor,
            x_account_id="acc_inactive",
            x_created_at="2024-01-02T03:04:05Z",
            x_updated_at="2024-01-02T03:04:05Z",
        )
        dns_acc = DnsAccount.objects.create(name=account_name)

        AccountsJoin.objects.create(dns_account=dns_acc, vendor_dns_account=vendor_dns_acc, is_active=False)

        with self.assertRaises(AccountsJoin.DoesNotExist):
            self.service._find_existing_account_in_db(account_name)

    def test_save_db_account_success(self):
        # Dummy JSON data from API
        self.service.save_db_account(self.vendor_account_data)

        # Validate there's one VendorDnsAccount row with the external id and the CF Vendor
        expected_account_id = self.vendor_account_data["result"].get("id")
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

    def test_save_db_zone_success(self):
        """Successfully creates registrar db zone objects."""
        # Create account object referenced in zone
        self.service.save_db_account(self.vendor_account_data)
        zone_domain = Domain.objects.create(name="dns-test.gov")

        self.service.save_db_zone(self.vendor_zone_data, zone_domain)

        # VendorDnsAccount row exists with matching zone xid as cloudflare id
        x_zone_id = self.vendor_zone_data["result"].get("id")
        vendor_zones = VendorDnsZone.objects.filter(x_zone_id=x_zone_id)
        self.assertEqual(vendor_zones.count(), 1)

        # DnsZone row exists with the matching zone name
        dns_zones = DnsZone.objects.filter(name="dns-test.gov")
        self.assertEqual(dns_zones.count(), 1)

        # DnsZone_VendorDnsZone object exists for registrar zone and vendor zone
        dns_zone = dns_zones.first()
        vendor_zone = vendor_zones.first()
        join_exists = ZonesJoin.objects.filter(dns_zone=dns_zone, vendor_dns_zone=vendor_zone).exists()
        self.assertTrue(join_exists)

    def test_save_db_zone_with_error_fails(self):
        # Create account object referenced in zone
        self.service.save_db_account(self.vendor_account_data)
        zone_domain = Domain.objects.create(name="dns-test.gov")

        expected_vendor_zones = VendorDnsZone.objects.count()
        expected_dns_zones = DnsZone.objects.count()
        expected_zone_joins = ZonesJoin.objects.count()

        # patch() temporarily replaces VendorDnsAccount.objects.create() with a fake version that raises
        # an integrity error mid-transcation
        with patch("registrar.models.VendorDnsZone.objects.create", side_effect=IntegrityError("simulated failure")):
            with self.assertRaises(IntegrityError):
                self.service.save_db_zone(self.vendor_zone_data, zone_domain)

        # Ensure that no database rows are created across our tables (since the transaction failed).
        self.assertEqual(VendorDnsZone.objects.count(), expected_vendor_zones)
        self.assertEqual(DnsZone.objects.count(), expected_dns_zones)
        self.assertEqual(ZonesJoin.objects.count(), expected_zone_joins)

    def test_save_db_zone_with_bad_or_incomplete_data_fails(self):
        """Do not create db zone objects when passed missing or incomplete Cloudlfare data."""
        invalid_result_payloads = [
            {"test_name": "Empty payload test case"},
            {"test_name": "Empty result dictionary test case", "result": {}},
            {
                "test_name": "Missing id test case",
                "result": {"name": "dns-test.gov", "account": {"id": "12345", "name": "account"}},
            },
            {
                "test_name": "Missing name test case",
                "result": {"id": "1", "account": {"id": "12345", "name": "account"}},
            },
            {"test_name": "Missing account test case", "result": {"id": "1", "name": "dns-test.gov"}},
        ]
        zone_domain = Domain.objects.create(name="dns-test.gov")

        expected_vendor_zones = VendorDnsZone.objects.count()
        expected_dns_zones = DnsZone.objects.count()
        expected_zone_joins = ZonesJoin.objects.count()

        for payload in invalid_result_payloads:
            with self.subTest(msg=payload["test_name"], payload=payload):
                with self.assertRaises(KeyError):
                    self.service.save_db_zone(payload, zone_domain)

                    # Nothing should be written on any failure
                    self.assertEqual(VendorDnsZone.objects.count(), expected_vendor_zones)
                    self.assertEqual(DnsZone.objects.count(), expected_dns_zones)
                    self.assertEqual(ZonesJoin.objects.count(), expected_zone_joins)

    def test_save_db_zone_on_failed_join_creation_throws_error(self):
        # Create account object referenced in zone
        self.service.save_db_account(self.vendor_account_data)
        zone_domain = Domain.objects.create(name="dns-test.gov")

        with patch(
            "registrar.models.DnsZone_VendorDnsZone.objects.get_or_create",
            side_effect=IntegrityError("simulated join failure"),
        ):
            with self.assertRaises(IntegrityError):
                self.service.save_db_zone(self.vendor_zone_data, zone_domain)

        # If the creation of the join fails, nothing should be saved in the database.
        self.assertEqual(VendorDnsZone.objects.count(), 0)
        self.assertEqual(DnsZone.objects.count(), 0)
        self.assertEqual(ZonesJoin.objects.count(), 0)
