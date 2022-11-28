from django.test import TestCase
from django.db.utils import IntegrityError

from registrar.models import Contact, DomainApplication, User, Website, Domain
from unittest import skip


class TestDomainApplication(TestCase):
    def test_empty_create_fails(self):
        """Can't create a completely empty domain application."""
        with self.assertRaisesRegex(IntegrityError, "creator"):
            DomainApplication.objects.create()

    def test_minimal_create(self):
        """Can create with just a creator."""
        user, _ = User.objects.get_or_create()
        application = DomainApplication.objects.create(creator=user)
        self.assertEquals(application.status, DomainApplication.STARTED)

    def test_full_create(self):
        """Can create with all fields."""
        user, _ = User.objects.get_or_create()
        contact = Contact.objects.create()
        com_website, _ = Website.objects.get_or_create(website="igorville.com")
        gov_website, _ = Website.objects.get_or_create(website="igorville.gov")
        domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        application = DomainApplication.objects.create(
            creator=user,
            investigator=user,
            organization_type=DomainApplication.FEDERAL,
            federal_branch=DomainApplication.EXECUTIVE,
            is_election_office=False,
            organization_name="Test",
            street_address="100 Main St.",
            unit_type="APT",
            unit_number="1A",
            state_territory="CA",
            zip_code="12345-6789",
            authorizing_official=contact,
            requested_domain=domain,
            submitter=contact,
            purpose="Igorville rules!",
            security_email="security@igorville.gov",
            anything_else="All of Igorville loves the dotgov program.",
            acknowledged_policy=True,
        )
        application.current_websites.add(com_website)
        application.alternative_domains.add(gov_website)
        application.other_contacts.add(contact)
        application.save()

    def test_status_fsm_submit_fail(self):
        user, _ = User.objects.get_or_create()
        application = DomainApplication.objects.create(creator=user)
        with self.assertRaises(ValueError):
            # can't submit an application with a null domain name
            application.submit()

    def test_status_fsm_submit_succeed(self):
        user, _ = User.objects.get_or_create()
        site = Domain.objects.create(name="igorville.gov")
        application = DomainApplication.objects.create(
            creator=user, requested_domain=site
        )
        application.submit()
        self.assertEqual(application.status, application.SUBMITTED)


class TestDomain(TestCase):
    def test_empty_create_fails(self):
        """Can't create a completely empty domain."""
        with self.assertRaisesRegex(IntegrityError, "name"):
            Domain.objects.create()

    def test_minimal_create(self):
        """Can create with just a name."""
        domain = Domain.objects.create(name="igorville.gov")
        self.assertEquals(domain.is_active, False)

    def test_get_status(self):
        """Returns proper status based on `is_active`."""
        domain = Domain.objects.create(name="igorville.gov")
        domain.save()
        self.assertEquals(None, domain.status)
        domain.activate()
        domain.save()
        self.assertIn("ok", domain.status)

    def test_fsm_activate_fail_unique(self):
        """Can't activate domain if name is not unique."""
        d1, _ = Domain.objects.get_or_create(name="igorville.gov")
        d2, _ = Domain.objects.get_or_create(name="igorville.gov")
        d1.activate()
        d1.save()
        with self.assertRaises(ValueError):
            d2.activate()

    def test_fsm_activate_fail_unapproved(self):
        """Can't activate domain if application isn't approved."""
        d1, _ = Domain.objects.get_or_create(name="igorville.gov")
        user, _ = User.objects.get_or_create()
        application = DomainApplication.objects.create(creator=user)
        d1.domain_application = application
        d1.save()
        with self.assertRaises(ValueError):
            d1.activate()


@skip("Not implemented yet.")
class TestDomainApplicationLifeCycle(TestCase):
    def test_application_approval(self):
        # DomainApplication is created
        # test: Domain is created and is inactive
        # analyst approves DomainApplication
        # test: Domain is activated
        pass

    def test_application_rejection(self):
        # DomainApplication is created
        # test: Domain is created and is inactive
        # analyst rejects DomainApplication
        # test: Domain remains inactive
        pass

    def test_application_deleted_before_approval(self):
        # DomainApplication is created
        # test: Domain is created and is inactive
        # admin deletes DomainApplication
        # test: Domain is deleted; Hosts, HostIps and Nameservers are deleted
        pass

    def test_application_deleted_following_approval(self):
        # DomainApplication is created
        # test: Domain is created and is inactive
        # analyst approves DomainApplication
        # admin deletes DomainApplication
        # test: DomainApplication foreign key field on Domain is set to null
        pass

    def test_application_approval_with_conflicting_name(self):
        # DomainApplication #1 is created
        # test: Domain #1 is created and is inactive
        # analyst approves DomainApplication #1
        # test: Domain #1 is activated
        # DomainApplication #2 is created, with the same domain name string
        # test: Domain #2 is created and is inactive
        # analyst approves DomainApplication #2
        # test: error is raised
        # test: DomainApplication #1 remains approved
        # test: Domain #1 remains active
        # test: DomainApplication #2 remains in investigating
        # test: Domain #2 remains inactive
        pass

    def test_application_approval_with_network_errors(self):
        # TODO: scenario wherein application is approved,
        # but attempts to contact the registry to activate the domain fail
        pass
