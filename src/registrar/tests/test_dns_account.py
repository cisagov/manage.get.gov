from django.test import TestCase
from django.db import IntegrityError, transaction
from django.apps import apps

DnsAccount = apps.get_model("registrar", "DnsAccount")

class DnsAccountTest(TestCase):
    """
    Testing constraints on DnsAccount model
    """

    def setUp(self):
        self.dns_account = DnsAccount.objects.create(name="acct-base")
        self.dns_account.save()

    def test_dns_account_creation(self):
        try:
            DnsAccount.objects.create(name="second-acct")
        except IntegrityError as e:
            self.fail(f"Unexpected IntegrityError for unique name: {e}")

    def test_dns_account_name_is_unique(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DnsAccount.objects.create(name=self.dns_account.name)
    

    
    
    