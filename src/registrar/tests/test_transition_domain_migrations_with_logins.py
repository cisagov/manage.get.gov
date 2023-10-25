from django.test import TestCase
from django.db.utils import IntegrityError
from unittest.mock import patch

from registrar.models import (
    Contact,
    DomainApplication,
    DomainInformation,
    User,
    Website,
    Domain,
    DraftDomain,
    DomainInvitation,
    UserDomainRole,
)

import boto3_mocking  # type: ignore
from .common import MockSESClient, less_console_noise, completed_application
from django_fsm import TransitionNotAllowed

boto3_mocking.clients.register_handler("sesv2", MockSESClient)

@boto3_mocking.patching
class TestLogins(TestCase):

    """Test the retrieval of invitations."""

    def setUp(self):
        self.domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        self.email = "mayor@igorville.gov"
        self.invitation, _ = DomainInvitation.objects.get_or_create(
            email=self.email, domain=self.domain
        )
        self.user, _ = User.objects.get_or_create(email=self.email)

        # clean out the roles each time
        UserDomainRole.objects.all().delete()

    def test_user_logins(self):
        """A new user's first_login callback retrieves their invitations."""
        self.user.first_login()
        self.assertTrue(UserDomainRole.objects.get(user=self.user, domain=self.domain))
