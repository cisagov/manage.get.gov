"""
Feature being tested: Registry Integration

This file tests the various ways in which the registrar interacts with the registry.
"""
from typing import Mapping, Any
from django.test import TestCase
from django.db.utils import IntegrityError
from unittest.mock import MagicMock, patch, call
import datetime
from registrar.models import Domain

from unittest import skip
from registrar.models.domain_application import DomainApplication
from registrar.models.domain_information import DomainInformation
from registrar.models.draft_domain import DraftDomain
from registrar.models.public_contact import PublicContact
from registrar.models.user import User
from .common import MockEppLib
from django_fsm import TransitionNotAllowed  # type: ignore
from epplibwrapper import (
    commands,
    common,
    extensions,
    responses,
    RegistryError,
    ErrorCode,
)


class TestDomainCache(MockEppLib):
    def test_cache_sets_resets(self):
        """Cache should be set on getter and reset on setter calls"""
        domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        # trigger getter
        _ = domain.creation_date

        # getter should set the domain cache with a InfoDomain object
        # (see InfoDomainResult)
        self.assertEquals(domain._cache["auth_info"], self.mockDataInfoDomain.auth_info)
        self.assertEquals(domain._cache["cr_date"], self.mockDataInfoDomain.cr_date)
        status_list = [status.state for status in self.mockDataInfoDomain.statuses]
        self.assertEquals(domain._cache["statuses"], status_list)
        self.assertFalse("avail" in domain._cache.keys())

        # using a setter should clear the cache
        domain.expiration_date = datetime.date.today()
        self.assertEquals(domain._cache, {})

        # send should have been called only once
        self.mockedSendFunction.assert_has_calls(
            [
                call(
                    commands.InfoDomain(name="igorville.gov", auth_info=None),
                    cleaned=True,
                ),
            ],
            any_order=False,  # Ensure calls are in the specified order
        )

    def test_cache_used_when_avail(self):
        """Cache is pulled from if the object has already been accessed"""
        domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        cr_date = domain.creation_date

        # repeat the getter call
        cr_date = domain.creation_date

        # value should still be set correctly
        self.assertEqual(cr_date, self.mockDataInfoDomain.cr_date)
        self.assertEqual(domain._cache["cr_date"], self.mockDataInfoDomain.cr_date)

        # send was only called once & not on the second getter call
        expectedCalls = [
            call(
                commands.InfoDomain(name="igorville.gov", auth_info=None), cleaned=True
            ),
        ]

        self.mockedSendFunction.assert_has_calls(expectedCalls)

    def test_cache_nested_elements(self):
        """Cache works correctly with the nested objects cache and hosts"""
        domain, _ = Domain.objects.get_or_create(name="igorville.gov")

        # the cached contacts and hosts should be dictionaries of what is passed to them
        expectedContactsDict = {
            "id": self.mockDataInfoDomain.contacts[0].contact,
            "type": self.mockDataInfoDomain.contacts[0].type,
            "auth_info": self.mockDataInfoContact.auth_info,
            "cr_date": self.mockDataInfoContact.cr_date,
        }
        expectedHostsDict = {
            "name": self.mockDataInfoDomain.hosts[0],
            "cr_date": self.mockDataInfoHosts.cr_date,
        }

        # this can be changed when the getter for contacts is implemented
        domain._get_property("contacts")

        # check domain info is still correct and not overridden
        self.assertEqual(domain._cache["auth_info"], self.mockDataInfoDomain.auth_info)
        self.assertEqual(domain._cache["cr_date"], self.mockDataInfoDomain.cr_date)

        # check contacts
        self.assertEqual(domain._cache["_contacts"], self.mockDataInfoDomain.contacts)
        self.assertEqual(domain._cache["contacts"], [expectedContactsDict])

        # get and check hosts is set correctly
        domain._get_property("hosts")
        self.assertEqual(domain._cache["hosts"], [expectedHostsDict])
        self.assertEqual(domain._cache["contacts"], [expectedContactsDict])

        # invalidate cache
        domain._cache = {}

        # get host
        domain._get_property("hosts")
        self.assertEqual(domain._cache["hosts"], [expectedHostsDict])

        # get contacts
        domain._get_property("contacts")
        self.assertEqual(domain._cache["hosts"], [expectedHostsDict])
        self.assertEqual(domain._cache["contacts"], [expectedContactsDict])

    def tearDown(self) -> None:
        Domain.objects.all().delete()
        super().tearDown()


class TestDomainCreation(MockEppLib):
    """Rule: An approved domain application must result in a domain"""

    def test_approved_application_creates_domain_locally(self):
        """
        Scenario: Analyst approves a domain application
            When the DomainApplication transitions to approved
            Then a Domain exists in the database with the same `name`
            But a domain object does not exist in the registry
        """
        draft_domain, _ = DraftDomain.objects.get_or_create(name="igorville.gov")
        user, _ = User.objects.get_or_create()
        application = DomainApplication.objects.create(
            creator=user, requested_domain=draft_domain
        )
        # skip using the submit method
        application.status = DomainApplication.SUBMITTED
        # transition to approve state
        application.approve()
        # should hav information present for this domain
        domain = Domain.objects.get(name="igorville.gov")
        self.assertTrue(domain)
        self.mockedSendFunction.assert_not_called()

    def test_accessing_domain_properties_creates_domain_in_registry(self):
        """
        Scenario: A registrant checks the status of a newly approved domain
            Given that no domain object exists in the registry
            When a property is accessed
            Then Domain sends `commands.CreateDomain` to the registry
            And `domain.state` is set to `UNKNOWN`
            And `domain.is_active()` returns False
        """
        domain = Domain.objects.create(name="beef-tongue.gov")
        # trigger getter
        _ = domain.statuses

        # contacts = PublicContact.objects.filter(domain=domain,
        # type=PublicContact.ContactTypeChoices.REGISTRANT).get()

        # Called in _fetch_cache
        self.mockedSendFunction.assert_has_calls(
            [
                # TODO: due to complexity of the test, will return to it in
                # a future ticket
                # call(
                #     commands.CreateDomain(name="beef-tongue.gov",
                #     id=contact.registry_id, auth_info=None),
                #     cleaned=True,
                # ),
                call(
                    commands.InfoDomain(name="beef-tongue.gov", auth_info=None),
                    cleaned=True,
                ),
            ],
            any_order=False,  # Ensure calls are in the specified order
        )

        self.assertEqual(domain.state, Domain.State.UNKNOWN)
        self.assertEqual(domain.is_active(), False)

    @skip("assertion broken with mock addition")
    def test_empty_domain_creation(self):
        """Can't create a completely empty domain."""
        with self.assertRaisesRegex(IntegrityError, "name"):
            Domain.objects.create()

    def test_minimal_creation(self):
        """Can create with just a name."""
        Domain.objects.create(name="igorville.gov")

    @skip("assertion broken with mock addition")
    def test_duplicate_creation(self):
        """Can't create domain if name is not unique."""
        Domain.objects.create(name="igorville.gov")
        with self.assertRaisesRegex(IntegrityError, "name"):
            Domain.objects.create(name="igorville.gov")

    def tearDown(self) -> None:
        DomainInformation.objects.all().delete()
        DomainApplication.objects.all().delete()
        Domain.objects.all().delete()
        super().tearDown()


class TestDomainStatuses(MockEppLib):
    """Domain statuses are set by the registry"""

    def test_get_status(self):
        """Domain 'statuses' getter returns statuses by calling epp"""
        domain, _ = Domain.objects.get_or_create(name="chicken-liver.gov")
        # trigger getter
        _ = domain.statuses
        status_list = [status.state for status in self.mockDataInfoDomain.statuses]
        self.assertEquals(domain._cache["statuses"], status_list)

        # Called in _fetch_cache
        self.mockedSendFunction.assert_has_calls(
            [
                call(
                    commands.InfoDomain(name="chicken-liver.gov", auth_info=None),
                    cleaned=True,
                ),
            ],
            any_order=False,  # Ensure calls are in the specified order
        )

    def test_get_status_returns_empty_list_when_value_error(self):
        """Domain 'statuses' getter returns an empty list
        when value error"""
        domain, _ = Domain.objects.get_or_create(name="pig-knuckles.gov")

        def side_effect(self):
            raise KeyError

        patcher = patch("registrar.models.domain.Domain._get_property")
        mocked_get = patcher.start()
        mocked_get.side_effect = side_effect

        # trigger getter
        _ = domain.statuses

        with self.assertRaises(KeyError):
            _ = domain._cache["statuses"]
        self.assertEquals(_, [])

        patcher.stop()

    @skip("not implemented yet")
    def test_place_client_hold_sets_status(self):
        """Domain 'place_client_hold' method causes the registry to change statuses"""
        raise

    @skip("not implemented yet")
    def test_revert_client_hold_sets_status(self):
        """Domain 'revert_client_hold' method causes the registry to change statuses"""
        raise

    def tearDown(self) -> None:
        Domain.objects.all().delete()
        super().tearDown()


class TestDomainAvailable(MockEppLib):
    """Test Domain.available"""

    # No SetUp or tearDown necessary for these tests

    def test_domain_available(self):
        """
        Scenario: Testing whether an available domain is available
            Should return True

            Mock response to mimic EPP Response
            Validate CheckDomain command is called
            Validate response given mock
        """

        def side_effect(_request, cleaned):
            return MagicMock(
                res_data=[
                    responses.check.CheckDomainResultData(
                        name="available.gov", avail=True, reason=None
                    )
                ],
            )

        patcher = patch("registrar.models.domain.registry.send")
        mocked_send = patcher.start()
        mocked_send.side_effect = side_effect

        available = Domain.available("available.gov")
        mocked_send.assert_has_calls(
            [
                call(
                    commands.CheckDomain(
                        ["available.gov"],
                    ),
                    cleaned=True,
                )
            ]
        )
        self.assertTrue(available)
        patcher.stop()

    def test_domain_unavailable(self):
        """
        Scenario: Testing whether an unavailable domain is available
            Should return False

            Mock response to mimic EPP Response
            Validate CheckDomain command is called
            Validate response given mock
        """

        def side_effect(_request, cleaned):
            return MagicMock(
                res_data=[
                    responses.check.CheckDomainResultData(
                        name="unavailable.gov", avail=False, reason="In Use"
                    )
                ],
            )

        patcher = patch("registrar.models.domain.registry.send")
        mocked_send = patcher.start()
        mocked_send.side_effect = side_effect

        available = Domain.available("unavailable.gov")
        mocked_send.assert_has_calls(
            [
                call(
                    commands.CheckDomain(
                        ["unavailable.gov"],
                    ),
                    cleaned=True,
                )
            ]
        )
        self.assertFalse(available)
        patcher.stop()

    def test_domain_available_with_value_error(self):
        """
        Scenario: Testing whether an invalid domain is available
            Should throw ValueError

            Validate ValueError is raised
        """
        with self.assertRaises(ValueError):
            Domain.available("invalid-string")

    def test_domain_available_unsuccessful(self):
        """
        Scenario: Testing behavior when registry raises a RegistryError

            Validate RegistryError is raised
        """

        def side_effect(_request, cleaned):
            raise RegistryError(code=ErrorCode.COMMAND_SYNTAX_ERROR)

        patcher = patch("registrar.models.domain.registry.send")
        mocked_send = patcher.start()
        mocked_send.side_effect = side_effect

        with self.assertRaises(RegistryError):
            Domain.available("raises-error.gov")
        patcher.stop()


class TestRegistrantContacts(MockEppLib):
    """Rule: Registrants may modify their WHOIS data"""

    def setUp(self):
        """
        Background:
            Given the registrant is logged in
            And the registrant is the admin on a domain
        """
        super().setUp()
        self.domain, _ = Domain.objects.get_or_create(name="security.gov")

    def tearDown(self):
        super().tearDown()
        # self.contactMailingAddressPatch.stop()
        # self.createContactPatch.stop()

    def test_no_security_email(self):
        """
        Scenario: Registrant has not added a security contact email
            Given `domain.security_contact` has not been set to anything
            When the domain is created in the registry
            Then the domain has a valid security contact with CISA defaults
            And disclose flags are set to keep the email address hidden
        """

        # making a domain should make it domain
        expectedSecContact = PublicContact.get_default_security()
        expectedSecContact.domain = self.domain

        self.domain.pendingCreate()

        self.assertEqual(self.mockedSendFunction.call_count, 8)
        self.assertEqual(PublicContact.objects.filter(domain=self.domain).count(), 4)
        self.assertEqual(
            PublicContact.objects.get(
                domain=self.domain,
                contact_type=PublicContact.ContactTypeChoices.SECURITY,
            ).email,
            expectedSecContact.email,
        )

        id = PublicContact.objects.get(
            domain=self.domain,
            contact_type=PublicContact.ContactTypeChoices.SECURITY,
        ).registry_id

        expectedSecContact.registry_id = id
        expectedCreateCommand = self._convertPublicContactToEpp(
            expectedSecContact, disclose_email=False
        )
        expectedUpdateDomain = commands.UpdateDomain(
            name=self.domain.name,
            add=[
                common.DomainContact(
                    contact=expectedSecContact.registry_id, type="security"
                )
            ],
        )

        self.mockedSendFunction.assert_any_call(expectedCreateCommand, cleaned=True)
        self.mockedSendFunction.assert_any_call(expectedUpdateDomain, cleaned=True)

    def test_user_adds_security_email(self):
        """
        Scenario: Registrant adds a security contact email
            When `domain.security_contact` is set equal to a PublicContact with the
                chosen security contact email
            Then Domain sends `commands.CreateContact` to the registry
            And Domain sends `commands.UpdateDomain` to the registry with the newly
                created contact of type 'security'
        """
        # make a security contact that is a PublicContact
        self.domain.pendingCreate()  # make sure a security email already exists
        expectedSecContact = PublicContact.get_default_security()
        expectedSecContact.domain = self.domain
        expectedSecContact.email = "newEmail@fake.com"
        expectedSecContact.registry_id = "456"
        expectedSecContact.name = "Fakey McFakerson"

        # calls the security contact setter as if you did
        #  self.domain.security_contact=expectedSecContact
        expectedSecContact.save()

        # no longer the default email it should be disclosed
        expectedCreateCommand = self._convertPublicContactToEpp(
            expectedSecContact, disclose_email=True
        )

        expectedUpdateDomain = commands.UpdateDomain(
            name=self.domain.name,
            add=[
                common.DomainContact(
                    contact=expectedSecContact.registry_id, type="security"
                )
            ],
        )

        # check that send has triggered the create command for the contact
        receivedSecurityContact = PublicContact.objects.get(
            domain=self.domain, contact_type=PublicContact.ContactTypeChoices.SECURITY
        )

        self.assertEqual(receivedSecurityContact, expectedSecContact)
        self.mockedSendFunction.assert_any_call(expectedCreateCommand, cleaned=True)
        self.mockedSendFunction.assert_any_call(expectedUpdateDomain, cleaned=True)

    def test_security_email_is_idempotent(self):
        """
        Scenario: Registrant adds a security contact email twice, due to a UI glitch
            When `commands.CreateContact` and `commands.UpdateDomain` are sent
                to the registry twice with identical data
            Then no errors are raised in Domain
        """

        security_contact = self.domain.get_default_security_contact()
        security_contact.registry_id = "fail"
        security_contact.save()

        self.domain.security_contact = security_contact

        expectedCreateCommand = self._convertPublicContactToEpp(
            security_contact, disclose_email=False
        )

        expectedUpdateDomain = commands.UpdateDomain(
            name=self.domain.name,
            add=[
                common.DomainContact(
                    contact=security_contact.registry_id, type="security"
                )
            ],
        )
        expected_calls = [
            call(expectedCreateCommand, cleaned=True),
            call(expectedCreateCommand, cleaned=True),
            call(expectedUpdateDomain, cleaned=True),
        ]
        self.mockedSendFunction.assert_has_calls(expected_calls, any_order=True)
        self.assertEqual(PublicContact.objects.filter(domain=self.domain).count(), 1)

    def test_user_deletes_security_email(self):
        """
        Scenario: Registrant clears out an existing security contact email
            Given a domain exists in the registry with a user-added security email
            When `domain.security_contact` is set equal to a PublicContact with an empty
                security contact email
            Then Domain sends `commands.UpdateDomain` and `commands.DeleteContact`
                to the registry
            And the domain has a valid security contact with CISA defaults
            And disclose flags are set to keep the email address hidden
        """
        old_contact = self.domain.get_default_security_contact()

        old_contact.registry_id = "fail"
        old_contact.email = "user.entered@email.com"
        old_contact.save()
        new_contact = self.domain.get_default_security_contact()
        new_contact.registry_id = "fail"
        new_contact.email = ""
        self.domain.security_contact = new_contact

        firstCreateContactCall = self._convertPublicContactToEpp(
            old_contact, disclose_email=True
        )
        updateDomainAddCall = commands.UpdateDomain(
            name=self.domain.name,
            add=[
                common.DomainContact(contact=old_contact.registry_id, type="security")
            ],
        )
        self.assertEqual(
            PublicContact.objects.filter(domain=self.domain).get().email,
            PublicContact.get_default_security().email,
        )
        # this one triggers the fail
        secondCreateContact = self._convertPublicContactToEpp(
            new_contact, disclose_email=True
        )
        updateDomainRemCall = commands.UpdateDomain(
            name=self.domain.name,
            rem=[
                common.DomainContact(contact=old_contact.registry_id, type="security")
            ],
        )

        defaultSecID = (
            PublicContact.objects.filter(domain=self.domain).get().registry_id
        )
        default_security = PublicContact.get_default_security()
        default_security.registry_id = defaultSecID
        createDefaultContact = self._convertPublicContactToEpp(
            default_security, disclose_email=False
        )
        updateDomainWDefault = commands.UpdateDomain(
            name=self.domain.name,
            add=[common.DomainContact(contact=defaultSecID, type="security")],
        )

        expected_calls = [
            call(firstCreateContactCall, cleaned=True),
            call(updateDomainAddCall, cleaned=True),
            call(secondCreateContact, cleaned=True),
            call(updateDomainRemCall, cleaned=True),
            call(createDefaultContact, cleaned=True),
            call(updateDomainWDefault, cleaned=True),
        ]

        self.mockedSendFunction.assert_has_calls(expected_calls, any_order=True)

    def test_updates_security_email(self):
        """
        Scenario: Registrant replaces one valid security contact email with another
            Given a domain exists in the registry with a user-added security email
            When `domain.security_contact` is set equal to a PublicContact with a new
                security contact email
            Then Domain sends `commands.UpdateContact` to the registry
        """
        security_contact = self.domain.get_default_security_contact()
        security_contact.email = "originalUserEmail@gmail.com"
        security_contact.registry_id = "fail"
        security_contact.save()
        expectedCreateCommand = self._convertPublicContactToEpp(
            security_contact, disclose_email=True
        )

        expectedUpdateDomain = commands.UpdateDomain(
            name=self.domain.name,
            add=[
                common.DomainContact(
                    contact=security_contact.registry_id, type="security"
                )
            ],
        )
        security_contact.email = "changedEmail@email.com"
        security_contact.save()
        expectedSecondCreateCommand = self._convertPublicContactToEpp(
            security_contact, disclose_email=True
        )
        updateContact = self._convertPublicContactToEpp(
            security_contact, disclose_email=True, createContact=False
        )

        expected_calls = [
            call(expectedCreateCommand, cleaned=True),
            call(expectedUpdateDomain, cleaned=True),
            call(expectedSecondCreateCommand, cleaned=True),
            call(updateContact, cleaned=True),
        ]
        self.mockedSendFunction.assert_has_calls(expected_calls, any_order=True)
        self.assertEqual(PublicContact.objects.filter(domain=self.domain).count(), 1)

    @skip("not implemented yet")
    def test_update_is_unsuccessful(self):
        """
        Scenario: An update to the security contact is unsuccessful
            When an error is returned from epplibwrapper
            Then a user-friendly error message is returned for displaying on the web
        """
        raise


class TestRegistrantNameservers(TestCase):
    """Rule: Registrants may modify their nameservers"""

    def setUp(self):
        """
        Background:
            Given the registrant is logged in
            And the registrant is the admin on a domain
        """
        pass

    @skip("not implemented yet")
    def test_user_adds_one_nameserver(self):
        """
        Scenario: Registrant adds a single nameserver
            Given the domain has zero nameservers
            When `domain.nameservers` is set to an array of length 1
            Then `commands.CreateHost` and `commands.UpdateDomain` is sent
                to the registry
            And `domain.is_active` returns False
        """
        raise

    @skip("not implemented yet")
    def test_user_adds_two_nameservers(self):
        """
        Scenario: Registrant adds 2 or more nameservers, thereby activating the domain
            Given the domain has zero nameservers
            When `domain.nameservers` is set to an array of length 2
            Then `commands.CreateHost` and `commands.UpdateDomain` is sent
                to the registry
            And `domain.is_active` returns True
        """
        raise

    @skip("not implemented yet")
    def test_user_adds_too_many_nameservers(self):
        """
        Scenario: Registrant adds 14 or more nameservers
            Given the domain has zero nameservers
            When `domain.nameservers` is set to an array of length 14
            Then Domain raises a user-friendly error
        """
        raise

    @skip("not implemented yet")
    def test_user_removes_some_nameservers(self):
        """
        Scenario: Registrant removes some nameservers, while keeping at least 2
            Given the domain has 3 nameservers
            When `domain.nameservers` is set to an array containing nameserver #1 and #2
            Then `commands.UpdateDomain` and `commands.DeleteHost` is sent
                to the registry
            And `domain.is_active` returns True
        """
        raise

    @skip("not implemented yet")
    def test_user_removes_too_many_nameservers(self):
        """
        Scenario: Registrant removes some nameservers, bringing the total to less than 2
            Given the domain has 3 nameservers
            When `domain.nameservers` is set to an array containing nameserver #1
            Then `commands.UpdateDomain` and `commands.DeleteHost` is sent
                to the registry
            And `domain.is_active` returns False
        """
        raise

    @skip("not implemented yet")
    def test_user_replaces_nameservers(self):
        """
        Scenario: Registrant simultaneously adds and removes some nameservers
            Given the domain has 3 nameservers
            When `domain.nameservers` is set to an array containing nameserver #1 plus
                two new nameservers
            Then `commands.CreateHost` is sent to create #4 and #5
            And `commands.UpdateDomain` is sent to add #4 and #5 plus remove #2 and #3
            And `commands.DeleteHost` is sent to delete #2 and #3
        """
        raise

    @skip("not implemented yet")
    def test_user_cannot_add_subordinate_without_ip(self):
        """
        Scenario: Registrant adds a nameserver which is a subdomain of their .gov
            Given the domain exists in the registry
            When `domain.nameservers` is set to an array containing an entry
                with a subdomain of the domain and no IP addresses
            Then Domain raises a user-friendly error
        """
        raise

    @skip("not implemented yet")
    def test_user_updates_ips(self):
        """
        Scenario: Registrant changes IP addresses for a nameserver
            Given the domain exists in the registry
            And has a subordinate nameserver
            When `domain.nameservers` is set to an array containing that nameserver
                with a different IP address(es)
            Then `commands.UpdateHost` is sent to the registry
        """
        raise

    @skip("not implemented yet")
    def test_user_cannot_add_non_subordinate_with_ip(self):
        """
        Scenario: Registrant adds a nameserver which is NOT a subdomain of their .gov
            Given the domain exists in the registry
            When `domain.nameservers` is set to an array containing an entry
                which is not a subdomain of the domain and has IP addresses
            Then Domain raises a user-friendly error
        """
        raise

    @skip("not implemented yet")
    def test_nameservers_are_idempotent(self):
        """
        Scenario: Registrant adds a set of nameservers twice, due to a UI glitch
            When `commands.CreateHost` and `commands.UpdateDomain` are sent
                to the registry twice with identical data
            Then no errors are raised in Domain
        """
        # implementation note: this requires seeing what happens when these are actually
        # sent like this, and then implementing appropriate mocks for any errors the
        # registry normally sends in this case
        raise

    @skip("not implemented yet")
    def test_update_is_unsuccessful(self):
        """
        Scenario: An update to the nameservers is unsuccessful
            When an error is returned from epplibwrapper
            Then a user-friendly error message is returned for displaying on the web
        """
        raise


class TestRegistrantDNSSEC(MockEppLib):
    """Rule: Registrants may modify their secure DNS data"""

    # helper function to create UpdateDomainDNSSECExtention object for verification
    def createUpdateExtension(self, dnssecdata: extensions.DNSSECExtension):
        return commands.UpdateDomainDNSSECExtension(
            maxSigLife=dnssecdata.maxSigLife,
            dsData=dnssecdata.dsData,
            keyData=dnssecdata.keyData,
            remDsData=None,
            remKeyData=None,
            remAllDsKeyData=True,
        )

    def setUp(self):
        """
        Background:
            Given the analyst is logged in
            And a domain exists in the registry
        """
        super().setUp()
        # for the tests, need a domain in the unknown state
        self.domain, _ = Domain.objects.get_or_create(name="fake.gov")
        self.addDsData1 = {
            "keyTag": 1234,
            "alg": 3,
            "digestType": 1,
            "digest": "ec0bdd990b39feead889f0ba613db4adec0bdd99",
        }
        self.addDsData2 = {
            "keyTag": 2345,
            "alg": 3,
            "digestType": 1,
            "digest": "ec0bdd990b39feead889f0ba613db4adecb4adec",
        }
        self.keyDataDict = {
            "flags": 257,
            "protocol": 3,
            "alg": 1,
            "pubKey": "AQPJ////4Q==",
        }
        self.dnssecExtensionWithDsData: Mapping[str, Any] = {
            "dsData": [common.DSData(**self.addDsData1)]
        }
        self.dnssecExtensionWithMultDsData: Mapping[str, Any] = {
            "dsData": [
                common.DSData(**self.addDsData1),
                common.DSData(**self.addDsData2),
            ],
        }
        self.dnssecExtensionWithKeyData: Mapping[str, Any] = {
            "maxSigLife": 3215,
            "keyData": [common.DNSSECKeyData(**self.keyDataDict)],
        }

    def tearDown(self):
        Domain.objects.all().delete()
        super().tearDown()

    def test_user_adds_dnssec_data(self):
        """
        Scenario: Registrant adds DNSSEC data.
        Verify that both the setter and getter are functioning properly

        This test verifies:
        1 - setter calls UpdateDomain command
        2 - setter adds the UpdateDNSSECExtension extension to the command
        3 - setter causes the getter to call info domain on next get from cache
        4 - getter properly parses dnssecdata from InfoDomain response and sets to cache

        """

        def side_effect(_request, cleaned):
            return MagicMock(
                res_data=[self.mockDataInfoDomain],
                extensions=[
                    extensions.DNSSECExtension(**self.dnssecExtensionWithDsData)
                ],
            )

        patcher = patch("registrar.models.domain.registry.send")
        mocked_send = patcher.start()
        mocked_send.side_effect = side_effect

        self.domain.dnssecdata = self.dnssecExtensionWithDsData
        # get the DNS SEC extension added to the UpdateDomain command and
        # verify that it is properly sent
        # args[0] is the _request sent to registry
        args, _ = mocked_send.call_args
        # assert that the extension matches
        self.assertEquals(
            args[0].extensions[0],
            self.createUpdateExtension(
                extensions.DNSSECExtension(**self.dnssecExtensionWithDsData)
            ),
        )
        # test that the dnssecdata getter is functioning properly
        dnssecdata_get = self.domain.dnssecdata
        mocked_send.assert_has_calls(
            [
                call(
                    commands.UpdateDomain(
                        name="fake.gov",
                        nsset=None,
                        keyset=None,
                        registrant=None,
                        auth_info=None,
                    ),
                    cleaned=True,
                ),
                call(
                    commands.InfoDomain(
                        name="fake.gov",
                    ),
                    cleaned=True,
                ),
            ]
        )

        self.assertEquals(
            dnssecdata_get.dsData, self.dnssecExtensionWithDsData["dsData"]
        )

        patcher.stop()

    def test_dnssec_is_idempotent(self):
        """
        Scenario: Registrant adds DNS data twice, due to a UI glitch

        # implementation note: this requires seeing what happens when these are actually
        # sent like this, and then implementing appropriate mocks for any errors the
        # registry normally sends in this case

        This test verifies:
        1 - UpdateDomain command called twice
        2 - setter causes the getter to call info domain on next get from cache
        3 - getter properly parses dnssecdata from InfoDomain response and sets to cache

        """

        def side_effect(_request, cleaned):
            return MagicMock(
                res_data=[self.mockDataInfoDomain],
                extensions=[
                    extensions.DNSSECExtension(**self.dnssecExtensionWithDsData)
                ],
            )

        patcher = patch("registrar.models.domain.registry.send")
        mocked_send = patcher.start()
        mocked_send.side_effect = side_effect

        # set the dnssecdata once
        self.domain.dnssecdata = self.dnssecExtensionWithDsData
        # set the dnssecdata again
        self.domain.dnssecdata = self.dnssecExtensionWithDsData
        # test that the dnssecdata getter is functioning properly
        dnssecdata_get = self.domain.dnssecdata
        mocked_send.assert_has_calls(
            [
                call(
                    commands.UpdateDomain(
                        name="fake.gov",
                        nsset=None,
                        keyset=None,
                        registrant=None,
                        auth_info=None,
                    ),
                    cleaned=True,
                ),
                call(
                    commands.UpdateDomain(
                        name="fake.gov",
                        nsset=None,
                        keyset=None,
                        registrant=None,
                        auth_info=None,
                    ),
                    cleaned=True,
                ),
                call(
                    commands.InfoDomain(
                        name="fake.gov",
                    ),
                    cleaned=True,
                ),
            ]
        )

        self.assertEquals(
            dnssecdata_get.dsData, self.dnssecExtensionWithDsData["dsData"]
        )

        patcher.stop()

    def test_user_adds_dnssec_data_multiple_dsdata(self):
        """
        Scenario: Registrant adds DNSSEC data with multiple DSData.
        Verify that both the setter and getter are functioning properly

        This test verifies:
        1 - setter calls UpdateDomain command
        2 - setter adds the UpdateDNSSECExtension extension to the command
        3 - setter causes the getter to call info domain on next get from cache
        4 - getter properly parses dnssecdata from InfoDomain response and sets to cache

        """

        def side_effect(_request, cleaned):
            return MagicMock(
                res_data=[self.mockDataInfoDomain],
                extensions=[
                    extensions.DNSSECExtension(**self.dnssecExtensionWithMultDsData)
                ],
            )

        patcher = patch("registrar.models.domain.registry.send")
        mocked_send = patcher.start()
        mocked_send.side_effect = side_effect

        self.domain.dnssecdata = self.dnssecExtensionWithMultDsData
        # get the DNS SEC extension added to the UpdateDomain command
        # and verify that it is properly sent
        # args[0] is the _request sent to registry
        args, _ = mocked_send.call_args
        # assert that the extension matches
        self.assertEquals(
            args[0].extensions[0],
            self.createUpdateExtension(
                extensions.DNSSECExtension(**self.dnssecExtensionWithMultDsData)
            ),
        )
        # test that the dnssecdata getter is functioning properly
        dnssecdata_get = self.domain.dnssecdata
        mocked_send.assert_has_calls(
            [
                call(
                    commands.UpdateDomain(
                        name="fake.gov",
                        nsset=None,
                        keyset=None,
                        registrant=None,
                        auth_info=None,
                    ),
                    cleaned=True,
                ),
                call(
                    commands.InfoDomain(
                        name="fake.gov",
                    ),
                    cleaned=True,
                ),
            ]
        )

        self.assertEquals(
            dnssecdata_get.dsData, self.dnssecExtensionWithMultDsData["dsData"]
        )

        patcher.stop()

    def test_user_adds_dnssec_keydata(self):
        """
        Scenario: Registrant adds DNSSEC data.
        Verify that both the setter and getter are functioning properly

        This test verifies:
        1 - setter calls UpdateDomain command
        2 - setter adds the UpdateDNSSECExtension extension to the command
        3 - setter causes the getter to call info domain on next get from cache
        4 - getter properly parses dnssecdata from InfoDomain response and sets to cache

        """

        def side_effect(_request, cleaned):
            return MagicMock(
                res_data=[self.mockDataInfoDomain],
                extensions=[
                    extensions.DNSSECExtension(**self.dnssecExtensionWithKeyData)
                ],
            )

        patcher = patch("registrar.models.domain.registry.send")
        mocked_send = patcher.start()
        mocked_send.side_effect = side_effect

        self.domain.dnssecdata = self.dnssecExtensionWithKeyData
        # get the DNS SEC extension added to the UpdateDomain command
        # and verify that it is properly sent
        # args[0] is the _request sent to registry
        args, _ = mocked_send.call_args
        # assert that the extension matches
        self.assertEquals(
            args[0].extensions[0],
            self.createUpdateExtension(
                extensions.DNSSECExtension(**self.dnssecExtensionWithKeyData)
            ),
        )
        # test that the dnssecdata getter is functioning properly
        dnssecdata_get = self.domain.dnssecdata
        mocked_send.assert_has_calls(
            [
                call(
                    commands.UpdateDomain(
                        name="fake.gov",
                        nsset=None,
                        keyset=None,
                        registrant=None,
                        auth_info=None,
                    ),
                    cleaned=True,
                ),
                call(
                    commands.InfoDomain(
                        name="fake.gov",
                    ),
                    cleaned=True,
                ),
            ]
        )

        self.assertEquals(
            dnssecdata_get.keyData, self.dnssecExtensionWithKeyData["keyData"]
        )

        patcher.stop()

    def test_update_is_unsuccessful(self):
        """
        Scenario: An update to the dns data is unsuccessful
            When an error is returned from epplibwrapper
            Then a user-friendly error message is returned for displaying on the web
        """

        def side_effect(_request, cleaned):
            raise RegistryError(code=ErrorCode.PARAMETER_VALUE_RANGE_ERROR)

        patcher = patch("registrar.models.domain.registry.send")
        mocked_send = patcher.start()
        mocked_send.side_effect = side_effect

        # if RegistryError is raised, view formats user-friendly
        # error message if error is_client_error, is_session_error, or
        # is_server_error; so test for those conditions
        with self.assertRaises(RegistryError) as err:
            self.domain.dnssecdata = self.dnssecExtensionWithDsData
            self.assertTrue(
                err.is_client_error() or err.is_session_error() or err.is_server_error()
            )

        patcher.stop()


class TestAnalystClientHold(MockEppLib):
    """Rule: Analysts may suspend or restore a domain by using client hold"""

    def setUp(self):
        """
        Background:
            Given the analyst is logged in
            And a domain exists in the registry
        """
        super().setUp()
        # for the tests, need a domain in the ready state
        self.domain, _ = Domain.objects.get_or_create(
            name="fake.gov", state=Domain.State.READY
        )
        # for the tests, need a domain in the on_hold state
        self.domain_on_hold, _ = Domain.objects.get_or_create(
            name="fake-on-hold.gov", state=Domain.State.ON_HOLD
        )

    def tearDown(self):
        Domain.objects.all().delete()
        super().tearDown()

    def test_analyst_places_client_hold(self):
        """
        Scenario: Analyst takes a domain off the internet
            When `domain.place_client_hold()` is called
            Then `CLIENT_HOLD` is added to the domain's statuses
        """
        self.domain.place_client_hold()
        self.mockedSendFunction.assert_has_calls(
            [
                call(
                    commands.UpdateDomain(
                        name="fake.gov",
                        add=[
                            common.Status(
                                state=Domain.Status.CLIENT_HOLD,
                                description="",
                                lang="en",
                            )
                        ],
                        nsset=None,
                        keyset=None,
                        registrant=None,
                        auth_info=None,
                    ),
                    cleaned=True,
                )
            ]
        )
        self.assertEquals(self.domain.state, Domain.State.ON_HOLD)

    def test_analyst_places_client_hold_idempotent(self):
        """
        Scenario: Analyst tries to place client hold twice
            Given `CLIENT_HOLD` is already in the domain's statuses
            When `domain.place_client_hold()` is called
            Then Domain returns normally (without error)
        """
        self.domain_on_hold.place_client_hold()
        self.mockedSendFunction.assert_has_calls(
            [
                call(
                    commands.UpdateDomain(
                        name="fake-on-hold.gov",
                        add=[
                            common.Status(
                                state=Domain.Status.CLIENT_HOLD,
                                description="",
                                lang="en",
                            )
                        ],
                        nsset=None,
                        keyset=None,
                        registrant=None,
                        auth_info=None,
                    ),
                    cleaned=True,
                )
            ]
        )
        self.assertEquals(self.domain_on_hold.state, Domain.State.ON_HOLD)

    def test_analyst_removes_client_hold(self):
        """
        Scenario: Analyst restores a suspended domain
            Given `CLIENT_HOLD` is in the domain's statuses
            When `domain.remove_client_hold()` is called
            Then `CLIENT_HOLD` is no longer in the domain's statuses
        """
        self.domain_on_hold.revert_client_hold()
        self.mockedSendFunction.assert_has_calls(
            [
                call(
                    commands.UpdateDomain(
                        name="fake-on-hold.gov",
                        rem=[
                            common.Status(
                                state=Domain.Status.CLIENT_HOLD,
                                description="",
                                lang="en",
                            )
                        ],
                        nsset=None,
                        keyset=None,
                        registrant=None,
                        auth_info=None,
                    ),
                    cleaned=True,
                )
            ]
        )
        self.assertEquals(self.domain_on_hold.state, Domain.State.READY)

    def test_analyst_removes_client_hold_idempotent(self):
        """
        Scenario: Analyst tries to remove client hold twice
            Given `CLIENT_HOLD` is not in the domain's statuses
            When `domain.remove_client_hold()` is called
            Then Domain returns normally (without error)
        """
        self.domain.revert_client_hold()
        self.mockedSendFunction.assert_has_calls(
            [
                call(
                    commands.UpdateDomain(
                        name="fake.gov",
                        rem=[
                            common.Status(
                                state=Domain.Status.CLIENT_HOLD,
                                description="",
                                lang="en",
                            )
                        ],
                        nsset=None,
                        keyset=None,
                        registrant=None,
                        auth_info=None,
                    ),
                    cleaned=True,
                )
            ]
        )
        self.assertEquals(self.domain.state, Domain.State.READY)

    def test_update_is_unsuccessful(self):
        """
        Scenario: An update to place or remove client hold is unsuccessful
            When an error is returned from epplibwrapper
            Then a user-friendly error message is returned for displaying on the web
        """

        def side_effect(_request, cleaned):
            raise RegistryError(code=ErrorCode.OBJECT_STATUS_PROHIBITS_OPERATION)

        patcher = patch("registrar.models.domain.registry.send")
        mocked_send = patcher.start()
        mocked_send.side_effect = side_effect

        # if RegistryError is raised, admin formats user-friendly
        # error message if error is_client_error, is_session_error, or
        # is_server_error; so test for those conditions
        with self.assertRaises(RegistryError) as err:
            self.domain.place_client_hold()
            self.assertTrue(
                err.is_client_error() or err.is_session_error() or err.is_server_error()
            )

        patcher.stop()


class TestAnalystLock(TestCase):
    """Rule: Analysts may lock or unlock a domain to prevent or allow updates"""

    def setUp(self):
        """
        Background:
            Given the analyst is logged in
            And a domain exists in the registry
        """
        pass

    @skip("not implemented yet")
    def test_analyst_locks_domain(self):
        """
        Scenario: Analyst locks a domain to prevent edits or deletion
            When `domain.lock()` is called
            Then `CLIENT_DELETE_PROHIBITED` is added to the domain's statuses
            And `CLIENT_TRANSFER_PROHIBITED` is added to the domain's statuses
            And `CLIENT_UPDATE_PROHIBITED` is added to the domain's statuses
        """
        raise

    @skip("not implemented yet")
    def test_analyst_locks_domain_idempotent(self):
        """
        Scenario: Analyst tries to lock a domain twice
            Given `CLIENT_*_PROHIBITED` is already in the domain's statuses
            When `domain.lock()` is called
            Then Domain returns normally (without error)
        """
        raise

    @skip("not implemented yet")
    def test_analyst_removes_lock(self):
        """
        Scenario: Analyst unlocks a domain to allow deletion or edits
            Given `CLIENT_*_PROHIBITED` is in the domain's statuses
            When `domain.unlock()` is called
            Then `CLIENT_DELETE_PROHIBITED` is no longer in the domain's statuses
            And `CLIENT_TRANSFER_PROHIBITED` is no longer in the domain's statuses
            And `CLIENT_UPDATE_PROHIBITED` is no longer in the domain's statuses
        """
        raise

    @skip("not implemented yet")
    def test_analyst_removes_lock_idempotent(self):
        """
        Scenario: Analyst tries to unlock a domain twice
            Given `CLIENT_*_PROHIBITED` is not in the domain's statuses
            When `domain.unlock()` is called
            Then Domain returns normally (without error)
        """
        raise

    @skip("not implemented yet")
    def test_update_is_unsuccessful(self):
        """
        Scenario: An update to lock or unlock a domain is unsuccessful
            When an error is returned from epplibwrapper
            Then a user-friendly error message is returned for displaying on the web
        """
        raise


class TestAnalystDelete(MockEppLib):
    """Rule: Analysts may delete a domain"""

    def setUp(self):
        """
        Background:
            Given the analyst is logged in
            And a domain exists in the registry
        """
        super().setUp()
        self.domain, _ = Domain.objects.get_or_create(
            name="fake.gov", state=Domain.State.READY
        )
        self.domain_on_hold, _ = Domain.objects.get_or_create(
            name="fake-on-hold.gov", state=Domain.State.ON_HOLD
        )

    def tearDown(self):
        Domain.objects.all().delete()
        super().tearDown()

    def test_analyst_deletes_domain(self):
        """
        Scenario: Analyst permanently deletes a domain
            When `domain.deletedInEpp()` is called
            Then `commands.DeleteDomain` is sent to the registry
            And `state` is set to `DELETED`
        """
        # Put the domain in client hold
        self.domain.place_client_hold()
        # Delete it...
        self.domain.deletedInEpp()
        self.mockedSendFunction.assert_has_calls(
            [
                call(
                    commands.DeleteDomain(name="fake.gov"),
                    cleaned=True,
                )
            ]
        )

        # Domain itself should not be deleted
        self.assertNotEqual(self.domain, None)

        # Domain should have the right state
        self.assertEqual(self.domain.state, Domain.State.DELETED)

        # Cache should be invalidated
        self.assertEqual(self.domain._cache, {})

    def test_deletion_is_unsuccessful(self):
        """
        Scenario: Domain deletion is unsuccessful
            When a subdomain exists
            Then a client error is returned of code 2305
            And `state` is not set to `DELETED`
        """
        # Desired domain
        domain, _ = Domain.objects.get_or_create(
            name="failDelete.gov", state=Domain.State.ON_HOLD
        )
        # Put the domain in client hold
        domain.place_client_hold()

        # Delete it
        with self.assertRaises(RegistryError) as err:
            domain.deletedInEpp()
            self.assertTrue(
                err.is_client_error()
                and err.code == ErrorCode.OBJECT_ASSOCIATION_PROHIBITS_OPERATION
            )
        self.mockedSendFunction.assert_has_calls(
            [
                call(
                    commands.DeleteDomain(name="failDelete.gov"),
                    cleaned=True,
                )
            ]
        )

        # Domain itself should not be deleted
        self.assertNotEqual(domain, None)
        # State should not have changed
        self.assertEqual(domain.state, Domain.State.ON_HOLD)

    def test_deletion_ready_fsm_failure(self):
        """
        Scenario: Domain deletion is unsuccessful due to FSM rules
            Given state is 'ready'
            When `domain.deletedInEpp()` is called
            and domain is of `state` is `READY`
            Then an FSM error is returned
            And `state` is not set to `DELETED`
        """
        self.assertEqual(self.domain.state, Domain.State.READY)
        with self.assertRaises(TransitionNotAllowed) as err:
            self.domain.deletedInEpp()
            self.assertTrue(
                err.is_client_error()
                and err.code == ErrorCode.OBJECT_STATUS_PROHIBITS_OPERATION
            )
        # Domain should not be deleted
        self.assertNotEqual(self.domain, None)
        # Domain should have the right state
        self.assertEqual(self.domain.state, Domain.State.READY)
