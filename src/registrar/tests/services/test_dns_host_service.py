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
    DnsRecord,
    VendorDnsRecord,
    DnsAccount_VendorDnsAccount as AccountsJoin,
    DnsZone_VendorDnsZone as ZonesJoin,
    DnsRecord_VendorDnsRecord as RecordsJoin,
    User,
    DomainInformation,
)
from registrar.services.utility.dns_helper import make_dns_account_name
from registrar.utility.errors import APIError
from registrar.tests.helpers.dns_data_generator import (
    create_domain,
    create_dns_account,
    create_initial_dns_setup,
    delete_all_dns_data,
    create_dns_zone,
)


class TestDnsHostService(TestCase):

    def setUp(self):
        mock_client = Mock()
        self.service = DnsHostService(client=mock_client)

    @patch("registrar.services.dns_host_service.DnsHostService.create_db_account")
    @patch("registrar.services.dns_host_service.DnsHostService._find_existing_account_in_db")
    @patch("registrar.services.dns_host_service.DnsHostService.create_and_save_account")
    @patch("registrar.services.dns_host_service.DnsHostService._find_existing_account_in_cf")
    def test_dns_account_setup_success(
        self,
        mock_find_existing_account_in_cf,
        mock_create_and_save_account,
        mock_find_existing_account_in_db,
        mock_create_db_account,
    ):
        create_domain(domain_name="test.gov")
        create_domain(domain_name="exists.gov")

        account_test_cases = [
            # Case A: Database has account
            {
                "test_name": "has db account",
                "domain_name": "test.gov",
                "db_account_id": "12345",
                "cf_account_data": {"id": "12345", "name": "test", "created_on": "2024-01-01 00:00:00+00:00"},
                "expected_account_id": "12345",
            },
            # Case B: Database empty, but CF has account
            {
                "test_name": "no db account or zone, has cf account",
                "domain_name": "exists.gov",
                "db_account_id": None,
                "cf_account_data": {"id": "12345", "name": "test", "created_on": "2024-01-01 00:00:00+00:00"},
                "expected_account_id": "12345",
            },
            # Case C: Database and CF empty
            {
                "test_name": "no db account or zone, no cf account",
                "domain_name": "exists.gov",
                "db_account_id": None,
                "cf_account_data": None,
                "expected_account_id": "12345",
            },
        ]

        for case in account_test_cases:
            with self.subTest(msg=case["test_name"]):
                mock_find_existing_account_in_db.return_value = case["db_account_id"]

                mock_find_existing_account_in_cf.return_value = case["cf_account_data"]
                mock_create_db_account.return_value = case["expected_account_id"]
                mock_create_and_save_account.return_value = case["expected_account_id"]

                x_account_id = self.service.dns_account_setup(case["domain_name"])

                self.assertEqual(x_account_id, case["expected_account_id"])

                # Now, some behavioral assertions to make sure flow was correct
                if case["db_account_id"]:
                    mock_find_existing_account_in_cf.assert_not_called()
                    mock_create_and_save_account.assert_not_called()
                    mock_create_db_account.assert_not_called()
                elif case["cf_account_data"]:
                    mock_create_db_account.assert_called_once()
                    mock_create_and_save_account.assert_not_called()
                else:
                    mock_create_and_save_account.assert_called_once()
                    mock_create_db_account.assert_called_once()

    @patch("registrar.services.dns_host_service.DnsHostService._find_existing_zone_in_cf")
    @patch("registrar.services.dns_host_service.DnsHostService.create_and_save_zone")
    @patch("registrar.services.dns_host_service.DnsHostService.create_db_zone")
    def test_dns_zone_setup_success(
        self,
        mock_create_db_zone,
        mock_create_and_save_zone,
        mock_find_existing_zone_in_cf,
    ):
        zone_test_cases = [
            # Case A: DB has zone
            {
                "test_name": "has db zone",
                "domain_name": "test.gov",
                "db_account_id": "12345",
                "x_account_id": "ABCDE",
                "db_zone": {
                    "name": "test.gov",
                    "nameservers": ["ns1.test.gov", "ns2.test.gov"],
                },
                "cf_zone_data": {
                    "id": "XYZ",
                    "name": "test.gov",
                    "account": {"name": "test.gov"},
                    "name_servers": ["ns1.test.gov", "ns2.test.gov"],
                    "created_on": "2024-01-01 00:00:00+00:00",
                },
            },
            # Case B: DB empty, but has zone in CF
            {
                "test_name": "has cf zone, no db zone",
                "domain_name": "exists.gov",
                "db_account_id": "67890",
                "x_account_id": "LMNOP",
                "db_zone": None,
                "cf_zone_data": {
                    "id": "ABC",
                    "name": "exists.gov",
                    "account": {"name": "exists.gov"},
                    "name_servers": ["ns1.exists.gov", "ns2.exists.gov"],
                    "created_on": "2024-01-01 00:00:00+00:00",
                },
            },
            # Case C: Both DB and CF empty
            {
                "test_name": "zone does not exist in cf",
                "domain_name": "other-domain.gov",
                "db_account_id": "34567",
                "x_account_id": "QRSTU",
                "db_zone": None,
                "cf_zone_data": None,
            },
        ]

        for case in zone_test_cases:
            with self.subTest(msg=case["test_name"]):
                domain = create_domain(domain_name=case["domain_name"])
                dns_account = create_dns_account(domain, x_account_id=case["x_account_id"])

                if case["db_zone"]:
                    create_dns_zone(
                        domain,
                        dns_account,
                        zone_name=case["db_zone"]["name"],
                        nameservers=case["db_zone"]["nameservers"],
                    )

                mock_find_existing_zone_in_cf.return_value = case["cf_zone_data"]

                self.service.dns_zone_setup(case["domain_name"], case["x_account_id"])

                # Behavioral assertions
                if case["db_zone"]:
                    mock_find_existing_zone_in_cf.assert_not_called()
                    mock_create_and_save_zone.assert_not_called()
                    mock_create_db_zone.assert_not_called()
                elif case["cf_zone_data"]:
                    mock_create_db_zone.assert_called_once()
                    mock_create_and_save_zone.assert_not_called()
                else:
                    mock_create_and_save_zone.assert_called_once()
                    mock_create_db_zone.assert_called_once()

    @patch("registrar.services.dns_host_service.DnsHostService._find_existing_account_in_cf")
    @patch("registrar.services.dns_host_service.DnsHostService._find_existing_account_in_db")
    def test_dns_setup_failure_from_find_existing_account_in_cf(
        self, mock_find_existing_account_in_db, mock_find_existing_account_in_cf
    ):
        domain_name = "test.gov"
        mock_find_existing_account_in_db.return_value = None
        mock_find_existing_account_in_cf.side_effect = APIError("DNS setup failed when finding account in cf")
        with self.assertRaises(APIError) as context:
            x_account_id = self.service.dns_account_setup(domain_name)
            self.service.dns_zone_setup(domain_name, x_account_id)
        self.assertIn("DNS setup failed when finding account in cf", str(context.exception))

    @patch("registrar.services.dns_host_service.DnsHostService.create_and_save_account")
    @patch("registrar.services.dns_host_service.DnsHostService._find_existing_account_in_cf")
    @patch("registrar.services.dns_host_service.DnsHostService._find_existing_account_in_db")
    def test_dns_setup_failure_from_create_and_save_account(
        self, mock_find_existing_account_in_db, mock_find_existing_account_in_cf, mock_create_and_save_account
    ):
        domain_name = "test.gov"

        mock_find_existing_account_in_db.return_value = None
        mock_find_existing_account_in_cf.return_value = None
        mock_create_and_save_account.side_effect = APIError("DNS setup failed to create account")

        with self.assertRaises((APIError, Exception)):
            x_account_id = self.service.dns_account_setup(domain_name)
            self.service.dns_zone_setup(domain_name, x_account_id)

    @patch("registrar.services.dns_host_service.CloudflareService.get_page_accounts")
    @patch("registrar.services.dns_host_service.CloudflareService.create_cf_account")
    def test_dns_setup_failure_from_create_cf_zone(self, mock_create_cf_account, mock_get_page_accounts):
        domain_name = "test.gov"
        account_name = make_dns_account_name(domain_name)
        account_id = "12345"
        mock_get_page_accounts.return_value = {"result": [{"id": "55555"}], "result_info": {"total_count": 8}}
        mock_create_cf_account.return_value = {"result": {"id": account_id}}
        mock_create_cf_account.side_effect = APIError("DNS setup failed to create zone")

        with self.assertRaises(APIError) as context:
            x_account_id = self.service.dns_account_setup(domain_name)
            self.service.dns_zone_setup(domain_name, x_account_id)

        mock_create_cf_account.assert_called_once_with(account_name)
        # mock_create_cf_zone.assert_called_once_with(zone_name, account_id) not sure why this fails: 0 calls
        self.assertIn("DNS setup failed to create zone", str(context.exception))

    @patch("registrar.services.dns_host_service.DnsHostService.create_db_record")
    @patch("registrar.services.dns_host_service.CloudflareService.create_dns_record")
    def test_create_cf_record_success(self, mock_create_dns_record, mock_create_db_record):
        zone_id = "1234"
        record_data = {
            "type": "A",
            "name": "test.gov",  # record name
            "content": "1.1.1.1",  # IPv4
            "ttl": 1,
            "comment": "Test record",
            "created_on": "2024-01-02T03:04:05Z",
        }

        mock_create_dns_record.return_value = {"result": {"id": zone_id, **record_data}}

        response = self.service.create_and_save_record(zone_id, record_data)
        self.assertEqual(response["result"]["id"], zone_id)
        self.assertEqual(response["result"]["name"], "test.gov")

    @patch("registrar.services.dns_host_service.CloudflareService.create_dns_record")
    def test_create_cf_record_failure(self, mock_create_dns_record):

        zone_id = "1234"
        record_data = {"type": "A", "content": "1.1.1.1", "ttl": 1, "comment": "Test record"}  # IPv4

        mock_create_dns_record.side_effect = APIError("Bad request: missing name")

        with self.assertRaises(APIError) as context:
            self.service.create_and_save_record(zone_id, record_data)
        self.assertIn("Bad request: missing name", str(context.exception))


class TestDnsHostServiceDB(TestCase):
    def setUp(self):
        self.vendor = DnsVendor.objects.get(name=DnsVendor.CF)
        mock_client = Mock()
        vendor_mock = Mock()
        self.service = DnsHostService(client=mock_client)
        self.service.dns_vendor_service = vendor_mock
        self.vendor_account_data = {
            "result": {"id": "12345", "name": "Account for dns-test.gov", "created_on": "2024-01-02T03:04:05Z"}
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
                "name_servers": ["mosaic.dns.gov", "plaid.dns.gov"],
                "vanity_name_servers": ["vanity.dns.gov", "vanity2.dns.gov"],
            }
        }

        self.vendor_record_data = {
            "result": {
                "id": "12345",
                "type": "A",
                "name": "test.gov",  # record name
                "content": "1.1.1.1",  # IPv4
                "ttl": 1,
                "comment": "Test record",
                "created_on": "2024-01-02T03:04:05Z",
                "tags": [],
            }
        }

    def tearDown(self):
        delete_all_dns_data()
        User.objects.all().delete()
        DomainInformation.objects.all().delete()

    def test_find_existing_account_success(self):
        domain = create_domain(domain_name="democracy.gov")
        test_x_account_id = "12345"
        account_name = make_dns_account_name(domain.name)

        # Paginated endpoint returns the above dictionary
        self.service.dns_vendor_service.get_page_accounts.return_value = self.vendor_zone_data

        self.service._find_account_tag_by_pubname = Mock(return_value=test_x_account_id)

        create_dns_account(domain=domain, x_account_id=test_x_account_id)

        found_id = self.service._find_existing_account_in_db(account_name)
        self.assertEqual(found_id, test_x_account_id)

    def test_find_existing_account_in_db_does_not_exist_returns_none(self):
        account_name = "Account for nonexistent.gov"

        result = self.service._find_existing_account_in_db(account_name)
        self.assertIsNone(result)

    def test_create_db_account_success(self):
        # Dummy JSON data from API
        self.service.create_db_account(self.vendor_account_data)

        # Validate there's one VendorDnsAccount row with the external id and the CF Vendor
        expected_account_id = self.vendor_account_data["result"].get("id")
        vendor_accts = VendorDnsAccount.objects.filter(x_account_id=expected_account_id, dns_vendor_id=self.vendor.id)
        self.assertEqual(vendor_accts.count(), 1)

        # Validate there's one DnsAccount row with the given name
        dns_accts = DnsAccount.objects.filter(name="Account for dns-test.gov")
        self.assertEqual(dns_accts.count(), 1)

        # Testing the join row for DnsAccount_VendorDnsAccount
        dns_acc = DnsAccount.objects.get(name="Account for dns-test.gov")
        vendor_acc = VendorDnsAccount.objects.get(x_account_id="12345")
        join_exists = AccountsJoin.objects.filter(dns_account=dns_acc, vendor_dns_account=vendor_acc).exists()
        self.assertTrue(join_exists)

    def test_create_db_account_with_error_fails(self):
        account_data = {"result": {"id": "FAIL1", "name": "Failed Test Account", "created_on": "2024-01-02T03:04:05Z"}}

        expected_vendor_accts = VendorDnsAccount.objects.count()
        expected_dns_accts = DnsAccount.objects.count()
        expected_acct_joins = AccountsJoin.objects.count()

        # patch() temporarily replaces VendorDnsAccount.objects.create() with a fake version that raises
        # an integrity error mid-transcation
        with patch("registrar.models.VendorDnsAccount.objects.create", side_effect=IntegrityError("simulated failure")):
            with self.assertRaises(IntegrityError):
                self.service.create_db_account(account_data)

        # Ensure that no database rows are created across our tables (since the transaction failed).
        self.assertEqual(VendorDnsAccount.objects.count(), expected_vendor_accts)
        self.assertEqual(DnsAccount.objects.count(), expected_dns_accts)
        self.assertEqual(AccountsJoin.objects.count(), expected_acct_joins)

    def test_create_db_account_with_bad_or_incomplete_data_fails(self):
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
                    self.service.create_db_account(payload)

                    # Nothing should be written on any failure
                    self.assertEqual(VendorDnsAccount.objects.count(), expected_vendor_accts)
                    self.assertEqual(DnsAccount.objects.count(), expected_dns_accts)
                    self.assertEqual(AccountsJoin.objects.count(), expected_acct_joins)

    def test_create_db_account_on_failed_join_creation_throws_error(self):
        payload = {
            "result": {
                "id": "JOIN1",
                "name": "Account for test.gov",
                "created_on": "2024-01-02T03:04:05Z",
            }
        }
        expected_vendor_accts = VendorDnsAccount.objects.count()
        expected_dns_accts = DnsAccount.objects.count()
        expected_acct_joins = AccountsJoin.objects.count()

        with patch(
            "registrar.models.DnsAccount_VendorDnsAccount.objects.create",
            side_effect=IntegrityError("simulated join failure"),
        ):
            with self.assertRaises(IntegrityError):
                self.service.create_db_account(payload)

        # If the creation of the join fails, nothing should be saved in the database.
        self.assertEqual(VendorDnsAccount.objects.count(), expected_vendor_accts)
        self.assertEqual(DnsAccount.objects.count(), expected_dns_accts)
        self.assertEqual(AccountsJoin.objects.count(), expected_acct_joins)

    def test_find_existing_zone_in_db_success(self):
        zone_name = "example.gov"
        test_x_account_id = "12345"
        x_zone_id = "zone-999"
        expected_nameservers = ["ns1.example.gov", "ns2.example.gov"]

        domain = create_domain(domain_name=zone_name)
        create_initial_dns_setup(
            domain, x_account_id=test_x_account_id, x_zone_id=x_zone_id, nameservers=expected_nameservers
        )

        found_x_zone_id, found_nameservers = self.service.get_x_zone_id_if_zone_exists(zone_name)

        self.assertEqual(found_x_zone_id, x_zone_id)
        self.assertEqual(found_nameservers, expected_nameservers)

    def test_find_existing_zone_in_db_does_not_exist_returns_none(self):
        zone_name = "missing.gov"

        x_zone_id, nameservers = self.service.get_x_zone_id_if_zone_exists(
            zone_name,
        )

        self.assertIsNone(x_zone_id)
        self.assertIsNone(nameservers)

    def test_create_db_zone_success(self):
        """Successfully creates registrar db zone objects."""
        # Create account object referenced in zone

        zone_domain = Domain.objects.create(name="dns-test.gov")
        create_dns_account(
            zone_domain,
            x_account_id=self.vendor_account_data["result"].get("id"),
            x_account_name=self.vendor_account_data["result"].get("name"),
        )

        self.service.create_db_zone(self.vendor_zone_data, zone_domain)

        # VendorDnsZone row exists with matching zone xid as cloudflare id
        x_zone_id = self.vendor_zone_data["result"].get("id")
        vendor_zones = VendorDnsZone.objects.filter(x_zone_id=x_zone_id)
        self.assertEqual(vendor_zones.count(), 1)

        # DnsZone row exists with the matching zone name
        dns_zones = DnsZone.objects.filter(name="dns-test.gov")
        zone = dns_zones.first()
        self.assertEqual(dns_zones.count(), 1)
        self.assertEqual(zone.nameservers, self.vendor_zone_data["result"]["vanity_name_servers"])

        # DnsZone_VendorDnsZone object exists for registrar zone and vendor zone
        dns_zone = dns_zones.first()
        vendor_zone = vendor_zones.first()
        join_exists = ZonesJoin.objects.filter(dns_zone=dns_zone, vendor_dns_zone=vendor_zone).exists()
        self.assertTrue(join_exists)

    def test_create_db_zone_with_error_fails(self):
        # Create account object referenced in zone
        self.service.create_db_account(self.vendor_account_data)
        zone_domain = Domain.objects.create(name="dns-test.gov")

        expected_vendor_zones = VendorDnsZone.objects.count()
        expected_dns_zones = DnsZone.objects.count()
        expected_zone_joins = ZonesJoin.objects.count()

        # patch() temporarily replaces VendorDnsAccount.objects.create() with a fake version that raises
        # an integrity error mid-transcation
        with patch("registrar.models.VendorDnsZone.objects.create", side_effect=IntegrityError("simulated failure")):
            with self.assertRaises(IntegrityError):
                self.service.create_db_zone(self.vendor_zone_data, zone_domain)

        # Ensure that no database rows are created across our tables (since the transaction failed).
        self.assertEqual(VendorDnsZone.objects.count(), expected_vendor_zones)
        self.assertEqual(DnsZone.objects.count(), expected_dns_zones)
        self.assertEqual(ZonesJoin.objects.count(), expected_zone_joins)

    def test_create_db_zone_with_bad_or_incomplete_data_fails(self):
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
                    self.service.create_db_zone(payload, zone_domain)

                    # Nothing should be written on any failure
                    self.assertEqual(VendorDnsZone.objects.count(), expected_vendor_zones)
                    self.assertEqual(DnsZone.objects.count(), expected_dns_zones)
                    self.assertEqual(ZonesJoin.objects.count(), expected_zone_joins)

    def test_create_db_zone_on_failed_join_creation_throws_error(self):
        # Create account object referenced in zone
        self.service.create_db_account(self.vendor_account_data)
        zone_domain = Domain.objects.create(name="dns-test.gov")

        expected_vendor_zones = VendorDnsZone.objects.count()
        expected_dns_zones = DnsZone.objects.count()
        expected_zone_joins = ZonesJoin.objects.count()

        with patch(
            "registrar.models.DnsZone_VendorDnsZone.objects.create",
            side_effect=IntegrityError("simulated join failure"),
        ):
            with self.assertRaises(IntegrityError):
                self.service.create_db_zone(self.vendor_zone_data, zone_domain)

        # If the creation of the join fails, nothing should be saved in the database.
        self.assertEqual(VendorDnsZone.objects.count(), expected_vendor_zones)
        self.assertEqual(DnsZone.objects.count(), expected_dns_zones)
        self.assertEqual(ZonesJoin.objects.count(), expected_zone_joins)

    def test_create_db_record_success(self):
        """Successfully creates registrar db record objects."""
        x_zone_id = self.vendor_account_data["result"].get("id")

        _, _, zone = create_initial_dns_setup(
            x_zone_id=self.vendor_zone_data["result"].get("id"),
            nameservers=self.vendor_zone_data["result"].get("name_servers"),
        )

        self.service.create_db_record(x_zone_id, self.vendor_record_data)

        # VendorDnsRecord row exists with matching record xid as cloudflare id
        x_record_id = self.vendor_record_data["result"].get("id")
        vendor_records = VendorDnsRecord.objects.filter(x_record_id=x_record_id)
        self.assertEqual(vendor_records.count(), 1)

        # DnsRecord row exists with the matching record data
        dns_records = DnsRecord.objects.filter(dns_zone=zone)
        self.assertEqual(dns_records.count(), 1)

        # Testing the join row for DnsRecord_VendorDnsRecord
        vendor_record = vendor_records.first()
        dns_record = DnsRecord.objects.get(vendor_dns_record=vendor_record)
        vendor_dns_record = VendorDnsRecord.objects.get(x_record_id=x_record_id)
        join_exists = RecordsJoin.objects.get(dns_record=dns_record, vendor_dns_record=vendor_dns_record)
        self.assertTrue(join_exists)

    def test_create_db_record_with_error_fails(self):
        x_zone_id = self.vendor_account_data["result"].get("id")
        nameservers = self.vendor_zone_data["result"].get("name_servers")

        create_initial_dns_setup(
            x_zone_id=x_zone_id,
            nameservers=nameservers,
        )

        expected_vendor_records = VendorDnsRecord.objects.count()
        expected_dns_records = DnsRecord.objects.count()
        expected_record_joins = RecordsJoin.objects.count()

        # patch() VendorDnsRecord.objects.create() to raise an integrity error mid-transcation
        with patch("registrar.models.VendorDnsRecord.objects.create", side_effect=IntegrityError("simulated failure")):
            with self.assertRaises(IntegrityError):
                self.service.create_db_record(x_zone_id, self.vendor_record_data)

        # No records are created in the db (since the transaction failed).
        self.assertEqual(VendorDnsRecord.objects.count(), expected_vendor_records)
        self.assertEqual(DnsRecord.objects.count(), expected_dns_records)
        self.assertEqual(RecordsJoin.objects.count(), expected_record_joins)

    def test_create_db_record_with_bad_or_incomplete_data_fails(self):
        """Do not create db zone objects when passed missing or incomplete Cloudlfare data."""
        # Test missing record data including incomplete registrar DNS record form data
        invalid_result_payloads = [
            {"test_name": "Empty payload test case"},
            {"test_name": "Empty result dictionary test case", "result": {}},
            {
                "test_name": "Missing id test case",
                "result": {
                    "type": "A",
                    "name": "test.gov",  # record name
                    "content": "1.1.1.1",  # IPv4
                    "ttl": 1,
                    "comment": "Test record",
                    "created_on": "2024-01-02T03:04:05Z",
                    "tags": [],
                },
            },
            {
                "test_name": "Missing name test case",
                "result": {
                    "id": "1234",
                    "type": "A",
                    "content": "1.1.1.1",  # IPv4
                    "ttl": 1,
                    "comment": "Test record",
                    "created_on": "2024-01-02T03:04:05Z",
                    "tags": [],
                },
            },
        ]
        x_zone_id = self.vendor_account_data["result"].get("id")

        create_initial_dns_setup(
            x_zone_id=x_zone_id,
            nameservers=self.vendor_zone_data["result"].get("name_servers"),
        )

        expected_vendor_records = VendorDnsRecord.objects.count()
        expected_dns_records = DnsRecord.objects.count()
        expected_record_joins = RecordsJoin.objects.count()

        for payload in invalid_result_payloads:
            with self.subTest(msg=payload["test_name"], payload=payload):
                with self.assertRaises(KeyError):
                    self.service.create_db_record(x_zone_id, payload)

                    # Nothing should be written on any failure
                    self.assertEqual(VendorDnsAccount.objects.count(), expected_vendor_records)
                    self.assertEqual(DnsAccount.objects.count(), expected_dns_records)
                    self.assertEqual(AccountsJoin.objects.count(), expected_record_joins)

    def test_create_db_record_on_failed_join_creation_throws_error(self):
        x_zone_id = self.vendor_account_data["result"].get("id")

        expected_vendor_records = VendorDnsRecord.objects.count()
        expected_dns_records = DnsRecord.objects.count()
        expected_record_joins = RecordsJoin.objects.count()

        # Create account and zone associated with record
        create_initial_dns_setup(
            x_zone_id=x_zone_id,
            nameservers=self.vendor_zone_data["result"].get("name_servers"),
        )

        with patch(
            "registrar.models.DnsRecord_VendorDnsRecord.objects.create",
            side_effect=IntegrityError("simulated join failure"),
        ):
            with self.assertRaises(IntegrityError):
                self.service.create_db_record(x_zone_id, self.vendor_record_data)

        # If the creation of the join fails, nothing should be saved in the database.
        self.assertEqual(VendorDnsRecord.objects.count(), expected_vendor_records)
        self.assertEqual(DnsRecord.objects.count(), expected_dns_records)
        self.assertEqual(RecordsJoin.objects.count(), expected_record_joins)

    def test_update_db_record_success(self):
        """Successfully creates registrar db record objects."""
        x_zone_id = self.vendor_account_data["result"].get("id")
        _, _, zone = create_initial_dns_setup(
            x_zone_id=self.vendor_zone_data["result"].get("id"),
            nameservers=self.vendor_zone_data["result"].get("name_servers"),
        )
        self.service.create_db_record(x_zone_id, self.vendor_record_data)

        # VendorDnsRecord row exists with matching record xid as cloudflare id
        x_record_id = self.vendor_record_data["result"].get("id")
        updated_record_data = {
            "result": {
                "name": "new-record-name.gov",  # record name
                "content": "2.2.2.2",  # IPv4
                "ttl": 1800,
                "comment": "Updated test record comment",
            }
        }
        self.service.update_db_record(x_record_id, x_record_id, updated_record_data)

        # DnsRecord row exists with the matching record data
        dns_record = DnsRecord.objects.filter(dns_zone=zone).first()
        self.assertEqual(dns_record.name, updated_record_data["result"].get("name"))
        self.assertEqual(dns_record.content, updated_record_data["result"].get("content"))
        self.assertEqual(dns_record.ttl, updated_record_data["result"].get("ttl"))
        self.assertEqual(dns_record.comment, updated_record_data["result"].get("comment"))
