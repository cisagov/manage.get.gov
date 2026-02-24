from django.core.management.base import BaseCommand
from httpx import Client
from registrar.services.dns_host_service import DnsHostService

class Command(BaseCommand):
    help = "Manually test update_account_dns_settings"

    def add_arguments(self, parser):
        parser.add_argument("x_account_id", type=str)

    def handle(self, *args, **options):
        service = DnsHostService(client=Client())
        resp = service.update_account_dns_settings(options["x_account_id"])
        self.stdout.write(f"success: {resp.success}")
        self.stdout.write(f"result: {resp.result}")
        self.stdout.write(f"errors: {resp.errors}")