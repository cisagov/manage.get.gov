from django.test import TestCase

from registrar.models import (
    User,
    Domain,
    DomainInvitation,
    UserDomainRole,
)


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

    def test_migration_functions(self):
        """ Run the master migration script using local test data """
        
        """ (analyze the tables just like the migration script does, but add assert statements) """
        #TODO: finish me!
        self.assertTrue(True)


    def test_user_logins(self):
        """A new user's first_login callback retrieves their invitations."""
        self.user.first_login()
        self.assertTrue(UserDomainRole.objects.get(user=self.user, domain=self.domain))
