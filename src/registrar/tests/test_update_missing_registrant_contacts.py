import logging
from registrar.models import Domain, DomainInformation
from registrar.models.public_contact import PublicContact
from registrar.utility.enums import DefaultEmail

from django.core.management import call_command
from unittest.mock import patch

from .common import create_user, MockEppLib

logger = logging.getLogger(__name__)


class TestUpdateMissingRegistrantContacts(MockEppLib):
    def setUp(self):
        super().setUp()
        self.user_one = create_user(username="testuser", email="testuser@example.gov")
        self.domain_one = Domain.objects.create(name="example.gov")
        self.domain_info_one = DomainInformation.objects.create(
            requester=self.user_one,
            domain=self.domain_one,
            organization_name="Cybersecurity and Infrastructure Security Agency",
            address_line1="1110 N. Glebe Rd",
            city="Arlington",
            state_territory="VA",
            zipcode="22201",
        )
        self.domain_two = Domain.objects.create(name="exampletwo.gov")
        self.domain_info_two = DomainInformation.objects.create(
            requester=self.user_one,
            domain=self.domain_two,
            organization_name="Cybersecurity and Infrastructure Security Agency",
            address_line1="1110 N. Glebe Rd",
            city="Arlington",
            state_territory="VA",
            zipcode="22201",
        )

        self.domain_three = Domain.objects.create(name="examplethree.gov")
        self.domain_info_three = DomainInformation.objects.create(
            requester=self.user_one,
            domain=self.domain_three,
            organization_name="Cybersecurity and Infrastructure Security Agency",
            address_line1="1110 N. Glebe Rd",
            city="Arlington",
            state_territory="VA",
            zipcode="22201",
        )

        self.contact_one = PublicContact(
            contact_type=PublicContact.ContactTypeChoices.REGISTRANT,
            name="Registrant CSD/CB – Attn: .gov TLD",
            org="Cybersecurity and Infrastructure Security Agency",
            street1="1110 N. Glebe Rd",
            city="Arlington",
            sp="VA",
            pc="22201",
            cc="US",
            email=DefaultEmail.PUBLIC_CONTACT_DEFAULT,
            voice="+1.8882820870",
            pw="thisisnotapassword",
        )
        
        self.contact_one.registry_id = "contact"
        self.contact_one.domain = self.domain_one

        self.contact_one.save(skip_epp_save=True)

    def test_command_update_missing_registrant_contacts_dry_run(self):
        with patch("registrar.models.domain.Domain.addRegistrant") as update_mock:
            call_command("update_missing_registrant_contacts", dry_run=True)
            self.assertEqual(
                Domain.objects.all().count(), 3
            )
            self.assertEqual(update_mock.call_count, 0)

    def test_command_update_missing_registrant_contacts_no_dry_run(self):
        with patch("registrar.models.domain.Domain.addRegistrant") as update_mock:
            call_command("update_missing_registrant_contacts", dry_run=False)
            self.assertEqual(
                Domain.objects.all().count(), 3
            )
            self.assertEqual(update_mock.call_count, 2)
    
    def test_command_update_missing_registrant_contacts_none_found(self):
        self.contact_two = PublicContact(
            contact_type=PublicContact.ContactTypeChoices.REGISTRANT,
            name="Registrant CSD/CB – Attn: .gov TLD",
            org="Cybersecurity and Infrastructure Security Agency",
            street1="1110 N. Glebe Rd",
            city="Arlington",
            sp="VA",
            pc="22201",
            cc="US",
            email=DefaultEmail.PUBLIC_CONTACT_DEFAULT,
            voice="+1.8882820870",
            pw="thisisnotapassword",
        )
        
        self.contact_two.registry_id = "contact"
        self.contact_two.domain = self.domain_two

        self.contact_two.save(skip_epp_save=True)

        self.contact_three = PublicContact(
            contact_type=PublicContact.ContactTypeChoices.REGISTRANT,
            name="Registrant CSD/CB – Attn: .gov TLD",
            org="Cybersecurity and Infrastructure Security Agency",
            street1="1110 N. Glebe Rd",
            city="Arlington",
            sp="VA",
            pc="22201",
            cc="US",
            email=DefaultEmail.PUBLIC_CONTACT_DEFAULT,
            voice="+1.8882820870",
            pw="thisisnotapassword",
        )
    
        self.contact_three.registry_id = "contact"
        self.contact_three.domain = self.domain_three

        self.contact_three.save(skip_epp_save=True)

    
        update_count = call_command("update_missing_registrant_contacts", dry_run=True)

        self.assertEqual(update_count, 0)
        
