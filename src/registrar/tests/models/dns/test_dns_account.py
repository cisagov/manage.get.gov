from django.test import TestCase
from django.db import IntegrityError, transaction

from registrar.models.dns.dns_account import DnsAccount
from registrar.models.dns.dns_account_vendor_dns_account import DnsAccount_VendorDnsAccount as AccountsJoin
from registrar.models.dns.dns_vendor import DnsVendor
from registrar.models.dns.vendor_dns_account import VendorDnsAccount


class DnsAccountTest(TestCase):

    def setUp(self):
        self.dns_account = DnsAccount.objects.create(name="acct-base")
        self.vendor = DnsVendor.objects.get(name=DnsVendor.CF)
        self.vendor_dns_account = VendorDnsAccount.objects.create(
            dns_vendor=self.vendor,
            x_account_id="12345",
            x_created_at="2025-10-17 19:57:53.157055+00",
            x_updated_at="2025-10-17 19:57:53.157055+00",
        )

    def tearDown(self):
        DnsAccount.objects.all().delete()

    def test_dns_account_creation_success(self):
        try:
            DnsAccount.objects.create(name="second-acct")
        except IntegrityError as e:
            self.fail(f"Unexpected IntegrityError for unique name: {e}")

    def test_dns_account_name_is_not_unique_throws_error(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DnsAccount.objects.create(name=self.dns_account.name)

    def test_get_x_account_id_success(self):
        AccountsJoin.objects.create(
            dns_account=self.dns_account,
            vendor_dns_account=self.vendor_dns_account,
            is_active=True,
        )
        self.assertEqual(self.dns_account.get_active_x_account_id, self.vendor_dns_account.x_account_id)

    def test_get_x_account_id_raises_error(self):
        AccountsJoin.objects.create(
            dns_account=self.dns_account,
            vendor_dns_account=self.vendor_dns_account,
            is_active=False,
        )
        with self.assertRaises(AccountsJoin.DoesNotExist):
            self.dns_account.get_active_x_account_id
