"""
Feature being tested: Registry Integration

This file tests the various ways in which the registrar interacts with the registry.
"""
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

from epplibwrapper import (
    commands,
    common,
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
            "addrs":self.mockDataInfoHosts.addrs,
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

        self.domain.dns_needed_from_unknown()

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
        # make sure a security email already exists
        self.domain.dns_needed_from_unknown()
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


class TestRegistrantNameservers(MockEppLib):
    """Rule: Registrants may modify their nameservers"""

    def setUp(self):
        """
        Background:
            Given the registrant is logged in
            And the registrant is the admin on a domain
        """
        super().setUp()
        self.nameserver1 = "ns1.my-nameserver-1.com"
        self.nameserver2 = "ns1.my-nameserver-2.com"
        self.nameserver3 = "ns1.cats-are-superior3.com"

        self.domain, _ = Domain.objects.get_or_create(
            name="my-nameserver.gov", state=Domain.State.DNS_NEEDED
        )

    def test_get_nameserver_changes_success_deleted_vals(self):
        # Testing only deleting and no other changes
        self.domain._cache["hosts"] = [
            {"name": "ns1.example.com", "addrs": None},
            {"name": "ns2.example.com", "addrs": ["1.2.3"]},
        ]
        newChanges = [
            ("ns1.example.com",),
        ]
        (
            deleted_values,
            updated_values,
            new_values,
            oldNameservers,
        ) = self.domain.getNameserverChanges(newChanges)

        self.assertEqual(deleted_values, [("ns2.example.com", ["1.2.3"])])
        self.assertEqual(updated_values, [])
        self.assertEqual(new_values, {})
        self.assertEqual(
            oldNameservers,
            {"ns1.example.com": None, "ns2.example.com": ["1.2.3"]},
        )

    def test_get_nameserver_changes_success_updated_vals(self):
        # Testing only updating no other changes
        self.domain._cache["hosts"] = [
            {"name": "ns3.my-nameserver.gov", "addrs": ["1.2.3"]},
        ]
        newChanges = [
            ("ns3.my-nameserver.gov", ["1.2.4"]),
        ]
        (
            deleted_values,
            updated_values,
            new_values,
            oldNameservers,
        ) = self.domain.getNameserverChanges(newChanges)

        self.assertEqual(deleted_values, [])
        self.assertEqual(updated_values, [("ns3.my-nameserver.gov", ["1.2.4"])])
        self.assertEqual(new_values, {})
        self.assertEqual(
            oldNameservers,
            {"ns3.my-nameserver.gov": ["1.2.3"]},
        )

    def test_get_nameserver_changes_success_new_vals(self):
        # Testing only creating no other changes
        self.domain._cache["hosts"] = [
            {"name": "ns1.example.com", "addrs": None},
        ]
        newChanges = [
            ("ns1.example.com",),
            ("ns4.example.com",),
        ]
        (
            deleted_values,
            updated_values,
            new_values,
            oldNameservers,
        ) = self.domain.getNameserverChanges(newChanges)

        self.assertEqual(deleted_values, [])
        self.assertEqual(updated_values, [])
        self.assertEqual(new_values, {"ns4.example.com": None})
        self.assertEqual(
            oldNameservers,
            {
                "ns1.example.com": None,
            },
        )

    def test_user_adds_one_nameserver(self):
        """
        Scenario: Registrant adds a single nameserver
            Given the domain has zero nameservers
            When `domain.nameservers` is set to an array of length 1
            Then `commands.CreateHost` and `commands.UpdateDomain` is sent
                to the registry
            And `domain.is_active` returns False
        """

        # set 1 nameserver
        nameserver = "ns1.my-nameserver.com"
        self.domain.nameservers = [(nameserver,)]

        # when we create a host, we should've updated at the same time
        created_host = commands.CreateHost(nameserver)
        update_domain_with_created = commands.UpdateDomain(
            name=self.domain.name, add=[common.HostObjSet([created_host.name])]
        )

        # checking if commands were sent (commands have to be sent in order)
        expectedCalls = [
            call(created_host, cleaned=True),
            call(update_domain_with_created, cleaned=True),
        ]

        self.mockedSendFunction.assert_has_calls(expectedCalls)

        # check that status is still NOT READY
        # as you have less than 2 nameservers
        self.assertFalse(self.domain.is_active())

    def test_user_adds_two_nameservers(self):
        """
        Scenario: Registrant adds 2 or more nameservers, thereby activating the domain
            Given the domain has zero nameservers
            When `domain.nameservers` is set to an array of length 2
            Then `commands.CreateHost` and `commands.UpdateDomain` is sent
                to the registry
            And `domain.is_active` returns True
        """

        # set 2 nameservers
        self.domain.nameservers = [(self.nameserver1,), (self.nameserver2,)]

        # when you create a host, you also have to update at same time
        created_host1 = commands.CreateHost(self.nameserver1)
        update_domain_with_created1 = commands.UpdateDomain(
            name=self.domain.name, add=[common.HostObjSet([created_host1.name])]
        )

        created_host2 = commands.CreateHost(self.nameserver2)
        update_domain_with_created2 = commands.UpdateDomain(
            name=self.domain.name, add=[common.HostObjSet([created_host2.name])]
        )

        infoDomain = commands.InfoDomain(name="my-nameserver.gov", auth_info=None)
        # checking if commands were sent (commands have to be sent in order)
        expectedCalls = [
            call(infoDomain, cleaned=True),
            call(created_host1, cleaned=True),
            call(update_domain_with_created1, cleaned=True),
            call(created_host2, cleaned=True),
            call(update_domain_with_created2, cleaned=True),
        ]

        self.mockedSendFunction.assert_has_calls(expectedCalls, any_order=True)
        self.assertEqual(5, self.mockedSendFunction.call_count)
        # check that status is READY
        self.assertTrue(self.domain.is_active())

    def test_user_adds_too_many_nameservers(self):
        """
        Scenario: Registrant adds 14 or more nameservers
            Given the domain has zero nameservers
            When `domain.nameservers` is set to an array of length 14
            Then Domain raises a user-friendly error
        """

        # set 13+ nameservers
        nameserver1 = "ns1.cats-are-superior1.com"
        nameserver2 = "ns1.cats-are-superior2.com"
        nameserver3 = "ns1.cats-are-superior3.com"
        nameserver4 = "ns1.cats-are-superior4.com"
        nameserver5 = "ns1.cats-are-superior5.com"
        nameserver6 = "ns1.cats-are-superior6.com"
        nameserver7 = "ns1.cats-are-superior7.com"
        nameserver8 = "ns1.cats-are-superior8.com"
        nameserver9 = "ns1.cats-are-superior9.com"
        nameserver10 = "ns1.cats-are-superior10.com"
        nameserver11 = "ns1.cats-are-superior11.com"
        nameserver12 = "ns1.cats-are-superior12.com"
        nameserver13 = "ns1.cats-are-superior13.com"
        nameserver14 = "ns1.cats-are-superior14.com"

        def _get_14_nameservers():
            self.domain.nameservers = [
                (nameserver1,),
                (nameserver2,),
                (nameserver3,),
                (nameserver4,),
                (nameserver5,),
                (nameserver6,),
                (nameserver7,),
                (nameserver8,),
                (nameserver9),
                (nameserver10,),
                (nameserver11,),
                (nameserver12,),
                (nameserver13,),
                (nameserver14,),
            ]

        self.assertRaises(ValueError, _get_14_nameservers)
        self.assertEqual(self.mockedSendFunction.call_count, 0)

    def test_user_removes_some_nameservers(self):
        """
        Scenario: Registrant removes some nameservers, while keeping at least 2
            Given the domain has 3 nameservers
            When `domain.nameservers` is set to an array containing nameserver #1 and #2
            Then `commands.UpdateDomain` and `commands.DeleteHost` is sent
                to the registry
            And `domain.is_active` returns True
        """

        # Mock is set to return 3 nameservers on infodomain
        self.extendedValues = True
        self.domain.nameservers = [(self.nameserver1,), (self.nameserver2,)]
        expectedCalls = [
            # calls info domain, and info on all hosts
            # to get past values
            # then removes the single host and updates domain
            call(
                commands.InfoDomain(name="my-nameserver.gov", auth_info=None),
                cleaned=True,
            ),
            call(commands.InfoHost(name="ns1.my-nameserver-1.com"), cleaned=True),
            call(commands.InfoHost(name="ns1.my-nameserver-2.com"), cleaned=True),
            call(commands.InfoHost(name="ns1.cats-are-superior3.com"), cleaned=True),
            call(
                commands.UpdateDomain(
                    name="my-nameserver.gov",
                    add=[],
                    rem=[common.HostObjSet(hosts=["ns1.cats-are-superior3.com"])],
                    nsset=None,
                    keyset=None,
                    registrant=None,
                    auth_info=None,
                ),
                cleaned=True,
            ),
            call(commands.DeleteHost(name="ns1.cats-are-superior3.com"), cleaned=True),
        ]

        self.mockedSendFunction.assert_has_calls(expectedCalls, any_order=True)
        self.assertTrue(self.domain.is_active())

    def test_user_removes_too_many_nameservers(self):
        """
        Scenario: Registrant removes some nameservers, bringing the total to less than 2
            Given the domain has 2 nameservers
            When `domain.nameservers` is set to an array containing nameserver #1
            Then `commands.UpdateDomain` and `commands.DeleteHost` is sent
                to the registry
            And `domain.is_active` returns False

        """
        self.extendedValues = True
        self.domain.ready()
        self.domain.nameservers = [(self.nameserver1,)]
        expectedCalls = [
            call(
                commands.InfoDomain(name="my-nameserver.gov", auth_info=None),
                cleaned=True,
            ),
            call(commands.InfoHost(name="ns1.my-nameserver-1.com"), cleaned=True),
            call(commands.InfoHost(name="ns1.my-nameserver-2.com"), cleaned=True),
            call(commands.InfoHost(name="ns1.cats-are-superior3.com"), cleaned=True),
            call(
                commands.UpdateDomain(
                    name="my-nameserver.gov",
                    add=[],
                    rem=[common.HostObjSet(hosts=["ns1.my-nameserver-2.com"])],
                    nsset=None,
                    keyset=None,
                    registrant=None,
                    auth_info=None,
                ),
                cleaned=True,
            ),
            call(commands.DeleteHost(name="ns1.my-nameserver-2.com"), cleaned=True),
            call(
                commands.UpdateDomain(
                    name="my-nameserver.gov",
                    add=[],
                    rem=[common.HostObjSet(hosts=["ns1.cats-are-superior3.com"])],
                    nsset=None,
                    keyset=None,
                    registrant=None,
                    auth_info=None,
                ),
                cleaned=True,
            ),
            call(commands.DeleteHost(name="ns1.cats-are-superior3.com"), cleaned=True),
        ]

        self.mockedSendFunction.assert_has_calls(expectedCalls, any_order=True)
        self.assertFalse(self.domain.is_active())

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
        self.extendedValues = True
        self.domain.ready()
        self.domain.nameservers = [
            (self.nameserver1,),
            ("ns1.cats-are-superior1.com",),
            ("ns1.cats-are-superior2.com",),
        ]

        expectedCalls = [
            call(
                commands.InfoDomain(name="my-nameserver.gov", auth_info=None),
                cleaned=True,
            ),
            call(commands.InfoHost(name="ns1.my-nameserver-1.com"), cleaned=True),
            call(commands.InfoHost(name="ns1.my-nameserver-2.com"), cleaned=True),
            call(commands.InfoHost(name="ns1.cats-are-superior3.com"), cleaned=True),
            call(
                commands.UpdateDomain(
                    name="my-nameserver.gov",
                    add=[],
                    rem=[common.HostObjSet(hosts=["ns1.my-nameserver-2.com"])],
                    nsset=None,
                    keyset=None,
                    registrant=None,
                    auth_info=None,
                ),
                cleaned=True,
            ),
            call(commands.DeleteHost(name="ns1.my-nameserver-2.com"), cleaned=True),
            call(
                commands.CreateHost(name="ns1.cats-are-superior1.com", addrs=[]),
                cleaned=True,
            ),
            call(
                commands.UpdateDomain(
                    name="my-nameserver.gov",
                    add=[common.HostObjSet(hosts=["ns1.cats-are-superior1.com"])],
                    rem=[],
                    nsset=None,
                    keyset=None,
                    registrant=None,
                    auth_info=None,
                ),
                cleaned=True,
            ),
            call(
                commands.CreateHost(name="ns1.cats-are-superior2.com", addrs=[]),
                cleaned=True,
            ),
            call(
                commands.UpdateDomain(
                    name="my-nameserver.gov",
                    add=[common.HostObjSet(hosts=["ns1.cats-are-superior2.com"])],
                    rem=[],
                    nsset=None,
                    keyset=None,
                    registrant=None,
                    auth_info=None,
                ),
                cleaned=True,
            ),
        ]

        self.mockedSendFunction.assert_has_calls(expectedCalls, any_order=True)
        self.assertTrue(self.domain.is_active())

    def test_user_cannot_add_subordinate_without_ip(self):
        """
        Scenario: Registrant adds a nameserver which is a subdomain of their .gov
            Given the domain exists in the registry
            When `domain.nameservers` is set to an array containing an entry
                with a subdomain of the domain and no IP addresses
            Then Domain raises a user-friendly error
        """

        dotgovnameserver = "my-nameserver.gov"

        with self.assertRaises(ValueError):
            self.domain.nameservers = [(dotgovnameserver,)]

    def test_user_updates_ips(self):
        """
        Scenario: Registrant changes IP addresses for a nameserver
            Given the domain exists in the registry
            And has a subordinate nameserver
            When `domain.nameservers` is set to an array containing that nameserver
                with a different IP address(es)
            Then `commands.UpdateHost` is sent to the registry
        """
        domain, _ = Domain.objects.get_or_create(
            name="nameserverwithip.gov", state=Domain.State.READY
        )
        domain.nameservers = [
            ("ns1.nameserverwithip.gov", ["2.3.4.5", "1.2.3.4"]),
            (
                "ns2.nameserverwithip.gov",
                ["1.2.3.4", "2.3.4.5", "2001:0db8:85a3:0000:0000:8a2e:0370:7334"],
            ),
            ("ns3.nameserverwithip.gov", ["2.3.4.5"]),
        ]

        expectedCalls = [
            call(
                commands.InfoDomain(name="nameserverwithip.gov", auth_info=None),
                cleaned=True,
            ),
            call(commands.InfoHost(name="ns1.nameserverwithip.gov"), cleaned=True),
            call(commands.InfoHost(name="ns2.nameserverwithip.gov"), cleaned=True),
            call(commands.InfoHost(name="ns3.nameserverwithip.gov"), cleaned=True),
            call(
                commands.UpdateHost(
                    name="ns2.nameserverwithip.gov",
                    add=[
                        common.Ip(
                            addr="2001:0db8:85a3:0000:0000:8a2e:0370:7334", ip="v6"
                        )
                    ],
                    rem=[],
                    chg=None,
                ),
                cleaned=True,
            ),
            call(
                commands.UpdateHost(
                    name="ns3.nameserverwithip.gov",
                    add=[],
                    rem=[common.Ip(addr="1.2.3.4", ip=None)],
                    chg=None,
                ),
                cleaned=True,
            ),
        ]

        self.mockedSendFunction.assert_has_calls(expectedCalls, any_order=True)
        self.assertTrue(domain.is_active())

    def test_user_cannot_add_non_subordinate_with_ip(self):
        """
        Scenario: Registrant adds a nameserver which is NOT a subdomain of their .gov
            Given the domain exists in the registry
            When `domain.nameservers` is set to an array containing an entry
                which is not a subdomain of the domain and has IP addresses
            Then Domain raises a user-friendly error
        """
        dotgovnameserver = "mynameserverdotgov.gov"

        with self.assertRaises(ValueError):
            self.domain.nameservers = [(dotgovnameserver, ["1.2.3"])]

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

        self.extendedValues = True

        # Checking that it doesn't create or update even if out of order
        self.domain.nameservers = [
            (self.nameserver3,),
            (self.nameserver1,),
            (self.nameserver2,),
        ]

        expectedCalls = [
            call(
                commands.InfoDomain(name="my-nameserver.gov", auth_info=None),
                cleaned=True,
            ),
            call(commands.InfoHost(name="ns1.my-nameserver-1.com"), cleaned=True),
            call(commands.InfoHost(name="ns1.my-nameserver-2.com"), cleaned=True),
            call(commands.InfoHost(name="ns1.cats-are-superior3.com"), cleaned=True),
        ]

        self.mockedSendFunction.assert_has_calls(expectedCalls, any_order=True)
        self.assertEqual(self.mockedSendFunction.call_count, 4)

    @skip("not implemented yet")
    def test_caching_issue(self):
        raise

    @skip("not implemented yet")
    def test_update_is_unsuccessful(self):
        """
        Scenario: An update to the nameservers is unsuccessful
            When an error is returned from epplibwrapper
            Then a user-friendly error message is returned for displaying on the web

        Note: TODO 433 -- we will perform correct error handling and complete
        this ticket. We want to raise an error for update/create/delete, but
        don't want to lose user info (and exit out too early)
        """

        domain, _ = Domain.objects.get_or_create(
            name="failednameserver.gov", state=Domain.State.READY
        )

        with self.assertRaises(RegistryError):
            domain.nameservers = [("ns1.failednameserver.gov", ["4.5.6"])]

        # print("self.mockedSendFunction.call_args_list is ")
        # print(self.mockedSendFunction.call_args_list)

    def tearDown(self):
        self.extendedValues = False
        return super().tearDown()


class TestRegistrantDNSSEC(TestCase):
    """Rule: Registrants may modify their secure DNS data"""

    def setUp(self):
        """
        Background:
            Given the registrant is logged in
            And the registrant is the admin on a domain
        """
        pass

    @skip("not implemented yet")
    def test_user_adds_dns_data(self):
        """
        Scenario: Registrant adds DNS data

        """
        raise

    @skip("not implemented yet")
    def test_dnssec_is_idempotent(self):
        """
        Scenario: Registrant adds DNS data twice, due to a UI glitch

        """
        # implementation note: this requires seeing what happens when these are actually
        # sent like this, and then implementing appropriate mocks for any errors the
        # registry normally sends in this case
        raise

    @skip("not implemented yet")
    def test_update_is_unsuccessful(self):
        """
        Scenario: An update to the dns data is unsuccessful
            When an error is returned from epplibwrapper
            Then a user-friendly error message is returned for displaying on the web
        """
        raise


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


class TestAnalystDelete(TestCase):
    """Rule: Analysts may delete a domain"""

    def setUp(self):
        """
        Background:
            Given the analyst is logged in
            And a domain exists in the registry
        """
        pass

    @skip("not implemented yet")
    def test_analyst_deletes_domain(self):
        """
        Scenario: Analyst permanently deletes a domain
            When `domain.delete()` is called
            Then `commands.DeleteDomain` is sent to the registry
            And `state` is set to `DELETED`
        """
        raise

    @skip("not implemented yet")
    def test_analyst_deletes_domain_idempotent(self):
        """
        Scenario: Analyst tries to delete an already deleted domain
            Given `state` is already `DELETED`
            When `domain.delete()` is called
            Then `commands.DeleteDomain` is sent to the registry
            And Domain returns normally (without error)
        """
        raise

    @skip("not implemented yet")
    def test_deletion_is_unsuccessful(self):
        """
        Scenario: Domain deletion is unsuccessful
            When an error is returned from epplibwrapper
            Then a user-friendly error message is returned for displaying on the web
            And `state` is not set to `DELETED`
        """
        raise
