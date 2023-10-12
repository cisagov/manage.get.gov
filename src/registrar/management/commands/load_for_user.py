"""Load fixture data for a single user by email address."""

import logging

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand

from auditlog.context import disable_auditlog

from registrar.fixtures import DomainApplicationFixture, DomainFixture


logger = logging.getLogger()


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("user_email", help="email address of the user")

    def handle(self, user_email, *args, **options):
        with disable_auditlog():
            User = get_user_model()
            this_user = User.objects.get(email=user_email)

            DomainApplicationFixture._create_domain_applications_for_user(this_user)
            DomainFixture._create_domains_for_user(this_user)

            logger.info(f"Loaded fixtures for {user_email}.")
