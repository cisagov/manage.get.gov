from django.test import TestCase
from django.db.utils import IntegrityError
from unittest.mock import patch, MagicMock
import datetime
from registrar.models import (
    DomainApplication,
    User,
    Domain,
    PublicContact
)
from unittest import skip
try:
    from epplib import InfoDomain
except ImportError:
    # allow epplibwrapper to load without epplib, for testing and development
    pass
##delete me
from django.core.cache import cache

class TestDomain(TestCase):
    mockDataInfoDomain={"avail": False,
                       "auth_info": None,
                       "cr_date": datetime.datetime(2023, 5, 25, 19, 45, 35)
                       }
    # {'auth_info': <MagicMock name='send().res_data.__getitem__().auth_info' id='281473717645712'>, '_contacts': <MagicMock name='send().res_data.__getitem__().contacts' id='281473717644608'>, 'cr_date': <MagicMock name='send().res_data.__getitem__().cr_date' id='281473719330096'>, 'ex_date': <MagicMock name='send().res_data.__getitem__().ex_date' id='281473719328464'>, '_hosts': <MagicMock name='send().res_data.__getitem__().hosts' id='281473721505856'>, 'name': <MagicMock name='send().res_data.__getitem__().name' id='281473717398512'>, 'registrant': <MagicMock name='send().res_data.__getitem__().registrant' id='281473717289408'>, 'statuses': <MagicMock name='send().res_data.__getitem__().statuses' id='281473717293632'>, 'tr_date': <MagicMock name='send().res_data.__getitem__().tr_date' id='281473710170096'>, 'up_date': <MagicMock name='send().res_data.__getitem__().up_date' id='281473710170384'>}

    # mockDataContactInfo={
    #                     "id": id,
    #                     "auth_info": getattr(data, "auth_info", ...),
    #                     "cr_date": getattr(data, "cr_date", ...),
    #                     "disclose": getattr(data, "disclose", ...),
    #                     "email": getattr(data, "email", ...),
    #                     "fax": getattr(data, "fax", ...),
    #                     "postal_info": getattr(data, "postal_info", ...),
    #                     "statuses": getattr(data, "statuses", ...),
    #                     "tr_date": getattr(data, "tr_date", ...),
    #                     "up_date": getattr(data, "up_date", ...),
    #                     "voice": getattr(data, "voice", ...),
    #                 }
    # mockDataHosts={
    #                     "name": name,
    #                     "addrs": getattr(data, "addrs", ...),
    #                     "cr_date": getattr(data, "cr_date", ...),
    #                     "statuses": getattr(data, "statuses", ...),
    #                     "tr_date": getattr(data, "tr_date", ...),
    #                     "up_date": getattr(data, "up_date", ...),
    #                 }
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
    def mock_send(self, _request, cleaned):
        print("*****IN MOCK******************")
        print(_request)
        print(_request.__class__)

        return MagicMock(res_data=[self.mockDataInfoDomain]       )
    # InfoDomainResult(code=1000, msg='Command completed successfully',
    #          res_data=[InfoDomainResultData(
    #         roid='DF13128E9-GOV', statuses=[Status(state='serverTransferProhibited', description=None, lang='en'), Status(state='inactive', description=None, lang='en')]
    #                                         , cl_id='cloudflare', cr_id=None, cr_date=datetime.datetime(2023, 5, 25, 19, 45, 35, tzinfo=tzlocal()), up_id=None, up_date=datetime.datetime(2023, 5, 30, 19, 45, 35, tzinfo=tzlocal()), tr_date=None, name='ok.gov', registrant='JOSWENSON', admins=[], nsset=None, keyset=None, ex_date=datetime.date(2024, 5, 25), )], cl_tr_id='b7p4gy#2023-06-11T23:39:36.563158', sv_tr_id='4tE5uQFmQ8KDKsgvlqpFxQ==-71', extensions=[], msg_q=None)}   
    # @patch('epplibwrapper.CLIENT')
    def test_cache(self):
        # print(patch)
        # domain, _= Domain.objects.get_or_create(name="igorville.gov")
        # mockSend=MagicMock(return_val)

       
        with patch ("registrar.models.domain.registry.send", new=self.mock_send):
        # with patch("epplibwrapper.CLIENT") as registry_mock, \
        #     patch("epplibwrapper.CLIENT.send",side_effects=self.mock_send) as send_mock:
            # with patch("epplibwrapper.CLIENT.send",side_effects=self.mock_send):
            domain, _ = Domain.objects.get_or_create(name="igorville.gov")
            domain._get_property("auth_info")
            print(domain._cache)
        # sec=domain.security_contact
        # print(sec) 
        # print("domain cache is as follows\n")

        # #would have expected the cache to contain the value 
        # print(domain._cache)
        # print("\n")
        # domain.registrant = 'abc123'
        # r=domain.registrant
        # print(domain._cache)
        





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
