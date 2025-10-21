from django.test import TestCase
from django.db import IntegrityError, transaction
from django.apps import apps

DnsAccount = apps.get_model("registrar", "DnsAccount")


class DnsAccountTest(TestCase):

    def setUp(self):
        self.dns_account = DnsAccount.objects.create(name="acct-base")
        self.dns_account.save()

    def test_dns_account_creation_success(self):
        try:
            DnsAccount.objects.create(name="second-acct")
        except IntegrityError as e:
            self.fail(f"Unexpected IntegrityError for unique name: {e}")

    def test_dns_account_name_is_not_unique_throws_error(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DnsAccount.objects.create(name=self.dns_account.name)
