from django.test import TestCase
from django.db.utils import IntegrityError

from registrar.models import Contact, DomainApplication, User, Website


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
            requested_domain=gov_website,
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
