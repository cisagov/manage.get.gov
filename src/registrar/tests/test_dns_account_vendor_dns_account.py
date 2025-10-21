from django.test import TestCase
from django.db import IntegrityError, transaction
from django.apps import apps

DnsAccount = apps.get_model("registrar", "DnsAccount")
VendorDnsAccount = apps.get_model("registrar", "VendorDnsAccount")
Join = apps.get_model("registrar", "DnsAccount_VendorDnsAccount")
DnsVendor = apps.get_model("registrar", "DnsVendor")


class DnsAccount_VendorDnsAccountTest(TestCase):
    """
    Testing constraints on DnsAccount_VendorDNSAccount model
    """

    def setUp(self):
        self.dns_account = DnsAccount.objects.create(name="acct-base")
        self.dns_account.save()
        self.vendor = DnsVendor.objects.create(name="Cloudflare")
        self.vendor.save()
        self.vendor_account_1 = VendorDnsAccount.objects.create(
            x_account_id="x1",
            x_created_at="2025-10-17 19:57:53.157055+00",
            x_updated_at="2025-10-17 19:57:53.157055+00",
            dns_vendor=self.vendor,
        )
        self.vendor_account_1.save()
        self.join1 = Join.objects.create(
            dns_account=self.dns_account, vendor_dns_account=self.vendor_account_1, is_active=True
        )

    def test_dns_account_name_is_unique(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DnsAccount.objects.create(name=self.dns_account.name)

    def test_is_active_constraint_throws_error(self):
        vendor_account_2 = VendorDnsAccount.objects.create(
            x_account_id="x2",
            x_created_at="2025-10-17 19:57:53.157055+00",
            x_updated_at="2025-10-17 19:57:53.157055+00",
            dns_vendor=self.vendor,
        )

        # Assert that an integrity error is raised when a second active join is created on the same DNS account.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Join.objects.create(
                    dns_account=self.dns_account,
                    vendor_dns_account=vendor_account_2,
                    is_active=True,
                )

    def test_is_active_constraint_passes(self):
        vendor_account_2 = VendorDnsAccount.objects.create(
            x_account_id="x2",
            x_created_at="2025-10-17 19:57:53.157055+00",
            x_updated_at="2025-10-17 19:57:53.157055+00",
            dns_vendor=self.vendor,
        )

        # Create a second join with is_active = False on the same DNS account (a valid join)
        second_join = Join.objects.create(
            dns_account=self.dns_account, vendor_dns_account=vendor_account_2, is_active=False
        )
        second_join.save()

        self.assertTrue(Join.objects.filter(pk=second_join.pk).exists(), "Second join created successfully!")
        self.assertTrue(
            Join.objects.filter(dns_account=self.dns_account, is_active=True).count() == 1,
            "Only one active join present for one dns_account.",
        )

    def test_update_is_active_constraint_throws_error(self):
        vendor_account_2 = VendorDnsAccount.objects.create(
            x_account_id="x2",
            x_created_at="2025-10-17 19:57:53.157055+00",
            x_updated_at="2025-10-17 19:57:53.157055+00",
            dns_vendor=self.vendor,
        )
        vendor_account_2.save()

        join2 = Join.objects.create(
            dns_account=self.dns_account,
            vendor_dns_account=vendor_account_2,
            is_active=False,
        )

        # Assert that the new join cannot be changed to active on update.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                join2.is_active = True
                join2.save()
