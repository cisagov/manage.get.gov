from django.test import TestCase
from django.db import IntegrityError, transaction
from django.apps import apps

DnsAccount = apps.get_model("registrar", "DnsAccount")
VendorDnsAccount = apps.get_model("registrar", "VendorDnsAccount")
Join = apps.get_model("registrar", "DNSAccount_VendorDnsAccount")

class DnsConstraintsTest(TestCase):
    def setUp(self):
        self.dns_account = DnsAccount.objects.create(name="acct-base")
        self.vendor1 = VendorDnsAccount.objects.create(x_account_id="x1")
        self.vendor2 = VendorDnsAccount.objects.create(x_account_id="x2")
    
    def test_dns_account_name_is_unique(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DnsAccount.objects.create(name=self.dns_account.name)
    
    def test_only_one_active_join_per_dns_account_on_create(self):
        # First active link works
        Join.objects.create(
            dns_account=self.dns_account, 
            vendor_dns_account=self.vendor1, 
            is_active=True,
        )

        # Second active for same dns_account must fail
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Join.objects.create(
                    dns_account=self.dns_account, 
                    vendor_dns_account=self.vendor2, 
                    is_active=True,
                )
        
        # Inactive is allowed alongside with active one
        Join.objects.create(
            dns_account=self.dns_account, 
            vendor_dns_account=self.vendor2, 
            is_active=False,
        )

    def test_cannot_flip_to_two_active_by_update(self):
        link1 = Join.objects.create(
            dns_account=self.dns_account, 
            vendor_dns_account=self.vendor1, 
            is_active=True,
        )
        link2 = Join.objects.create(
            dns_account=self.dns_account, 
            vendor_dns_account=self.vendor2, 
            is_active=False,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                link2.is_active = True
                link2.save()
    
