from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from registrar.models import Domain, DomainApplication


class TestLoadForUserCommand(TestCase):
    def setUp(self):
        # create a user to use
        self.user_email = "nope@nope.nope"
        User = get_user_model()
        User.objects.create(email=self.user_email)
        call_command("load_for_user", self.user_email)

    def test_creates_domain_applications(self):
        """Creates applications for this user."""
        self.assertGreater(
            len(DomainApplication.objects.filter(creator__email=self.user_email)), 0
        )

    def test_creates_domains(self):
        """Creates domains for this user."""
        self.assertGreater(
            len(Domain.objects.filter(permissions__user__email=self.user_email)), 0
        )
