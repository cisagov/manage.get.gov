from django.test import TestCase
from django.db.utils import IntegrityError
from unittest.mock import patch, MagicMock
import datetime
from registrar.models import (
    DomainApplication,
    User,
    Domain
)
from unittest import skip
from epplibwrapper import commands

class TestDomain(TestCase):
    class fakedEppObject(object):
        """"""
        def __init__(self, auth_info=..., cr_date=..., contacts=..., hosts=...):
            self.auth_info=auth_info
            self.cr_date=cr_date
            self.contacts=contacts
            self.hosts=hosts

    mockDataInfoDomain=fakedEppObject("fakepw",cr_date= datetime.datetime(2023, 5, 25, 19, 45, 35), contacts=["123"], hosts=["fake.host.com"])
    mockDataInfoContact=fakedEppObject("anotherPw", cr_date=datetime.datetime(2023, 7, 25, 19, 45, 35))
    mockDataInfoHosts=fakedEppObject("lastPw", cr_date=datetime.datetime(2023, 8, 25, 19, 45, 35))
    
    def mockSend(self, _request, cleaned):
        """"""
        if isinstance(_request,commands.InfoDomain):
            return MagicMock(res_data=[self.mockDataInfoDomain])
        elif isinstance(_request, commands.InfoContact):
            return MagicMock(res_data=[self.mockDataInfoContact])
        return MagicMock(res_data=[self.mockDataInfoHosts])
    
    def setUp(self):
        """mock epp send function as this will fail locally"""
        self.patcher = patch ("registrar.models.domain.registry.send")
        self.mock_foo = self.patcher.start()
        self.mock_foo.side_effect=self.mockSend

    def tearDown(self):
        self.patcher.stop()

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

    def test_cache_sets_resets(self):
        """Cache should be set on getter and reset on setter calls"""
        domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        #trigger getter
        _val=domain.creation_date
        
        #getter should set the domain cache with a InfoDomain object (see InfoDomainResult)
        self.assertEquals(domain._cache["auth_info"],self.mockDataInfoDomain.auth_info )
        self.assertEquals(domain._cache["cr_date"],self.mockDataInfoDomain.cr_date )
        self.assertFalse("avail" in domain._cache.keys())

        #using a setter should clear the cache
        domain.nameservers=[("","")]
        self.assertEquals(domain._cache, {})

        #send should have been called only once
        self.mock_foo.assert_called_once()

    def test_cache_used_when_avail(self):
        """Cache is pulled from if the object has already been accessed"""
        domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        cr_date=domain.creation_date
  
        #repeat the getter call  
        cr_date=domain.creation_date

        #value should still be set correctly 
        self.assertEqual(cr_date, self.mockDataInfoDomain.cr_date )
        self.assertEqual(domain._cache["cr_date"], self.mockDataInfoDomain.cr_date )

        #send was only called once & not on the second getter call
        self.mock_foo.assert_called_once()

    
    def test_cache_nested_elements(self):
        """Cache works correctly with the nested objects cache and hosts"""
        domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        
        #the cached contacts and hosts should be dictionaries of what is passed to them
        expectedContactsDict={'id':self.mockDataInfoDomain.contacts[0],
                              'auth_info':self.mockDataInfoContact.auth_info,
                              'cr_date':self.mockDataInfoContact.cr_date
                              }
        expectedHostsDict={'name':self.mockDataInfoDomain.hosts[0],
                           'cr_date':self.mockDataInfoHosts.cr_date}
        
        #this can be changed when the getter for contacts is implemented
        domain._get_property("contacts")
       
        #check domain info is still correct and not overridden
        self.assertEqual(domain._cache["auth_info"], self.mockDataInfoDomain.auth_info )
        self.assertEqual(domain._cache["cr_date"], self.mockDataInfoDomain.cr_date )

        #check contacts
        self.assertEqual(domain._cache["_contacts"], self.mockDataInfoDomain.contacts )
        self.assertEqual(domain._cache["contacts"], [expectedContactsDict])
        
        #get and check hosts is set correctly
        domain._get_property("hosts")
        self.assertEqual(domain._cache["hosts"], [expectedHostsDict])

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
