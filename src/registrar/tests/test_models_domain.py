from django.test import TestCase
from django.db.utils import IntegrityError

from registrar.models import (
    DomainApplication,
    User,
    Domain,
    PublicContact
)
from unittest import skip

##delete me
from django.core.cache import cache

class TestDomain(TestCase):
    def test_empty_create_fails(self):
        """Can't create a completely empty domain."""
        with self.assertRaisesRegex(IntegrityError, "name"):
            Domain.objects.create()

    def test_minimal_create(self):
        """Can create with just a name."""
        Domain.objects.create(name="igorville.gov")
        # this assertion will not work -- for now, the fact that the
        # above command didn't error out is proof enough
        # self.assertEquals(domain.state, Domain.State.DRAFTED)
    def test_cache(self):
        # domain, _= Domain.objects.get_or_create(name="igorville.gov")


        domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        sec=domain.security_contact
        print(sec) 
        print("domain cache is as follows\n")

        #would have expected the cache to contain the value 
        print(domain._cache)
        print("\n")
        domain.registrant = 'abc123'
        r=domain.registrant
        print(domain._cache)






    @skip("cannot activate a domain without mock registry")
    def test_get_status(self):
        """Returns proper status based on `state`."""
        domain = Domain.objects.create(name="igorville.gov")
        domain.save()
        self.assertEqual(None, domain.status)
        domain.activate()
        domain.save()
        self.assertIn("ok", domain.status)

    @skip("cannot activate a domain without mock registry")
    def test_fsm_activate_fail_unique(self):
        """Can't activate domain if name is not unique."""
        d1, _ = Domain.objects.get_or_create(name="igorville.gov")
        d2, _ = Domain.objects.get_or_create(name="igorville.gov")
        d1.activate()
        d1.save()
        with self.assertRaises(ValueError):
            d2.activate()

    @skip("cannot activate a domain without mock registry")
    def test_fsm_activate_fail_unapproved(self):
        """Can't activate domain if application isn't approved."""
        d1, _ = Domain.objects.get_or_create(name="igorville.gov")
        user, _ = User.objects.get_or_create()
        application = DomainApplication.objects.create(creator=user)
        d1.domain_application = application
        d1.save()
        with self.assertRaises(ValueError):
            d1.activate()
