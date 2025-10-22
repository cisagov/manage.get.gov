from django.test import TestCase
from django.db import IntegrityError, transaction

from registrar.models.dns.dns_account import DnsAccount


class DnsAccountTest(TestCase):

    def setUp(self):
        self.dns_account = DnsAccount.objects.create(name="acct-base")
        self.dns_account.save()

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
