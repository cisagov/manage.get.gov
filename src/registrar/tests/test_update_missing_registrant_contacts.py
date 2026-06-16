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
        self.userOne = create_user(username="testuser", email="testuser@example.gov")
        self.domainOne = Domain.objects.create(name="example.gov")
        self.domain_infoOne = DomainInformation.objects.create(
            requester=self.userOne,
            domain=self.domainOne,
            organization_name="Cybersecurity and Infrastructure Security Agency",
            address_line1="1110 N. Glebe Rd",
            city="Arlington",
            state_territory="VA",
            zipcode="22201",
        )
        self.domainTwo = Domain.objects.create(name="exampletwo.gov")
        self.domain_infoTwo = DomainInformation.objects.create(
            requester=self.userOne,
            domain=self.domainTwo,
            organization_name="Cybersecurity and Infrastructure Security Agency",
            address_line1="1110 N. Glebe Rd",
            city="Arlington",
            state_territory="VA",
            zipcode="22201",
        )

        self.contactOne = PublicContact(
            contact_type=PublicContact.ContactTypeChoices.ADMINISTRATIVE,
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
        self.contactTwo = PublicContact(
            contact_type=PublicContact.ContactTypeChoices.ADMINISTRATIVE,
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
        self.contactThree = PublicContact(
            contact_type=PublicContact.ContactTypeChoices.ADMINISTRATIVE,
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

        self.contactFour = PublicContact(
            contact_type=PublicContact.ContactTypeChoices.ADMINISTRATIVE,
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
        self.contactOne.registry_id = "contact"
        self.contactOne.domain = self.domainOne

        self.contactTwo.registry_id = "contact"
        self.contactTwo.domain = self.domainTwo

        self.contactOne.save(skip_epp_save=True)
        self.contactTwo.save(skip_epp_save=True)

    def test_command_update_missing_registrant_contacts_dry_run(self):
        with patch("registrar.models.domain.Domain.addRegistrant") as update_mock:
            call_command("update_missing_registrant_contacts", dry_run=True)
            self.assertEqual(
                PublicContact.objects.filter(contact_type=PublicContact.ContactTypeChoices.ADMINISTRATIVE).count(), 2
            )
            self.assertEqual(update_mock.call_count, 0)

    def test_command_update_missing_registrant_contacts_no_dry_run(self):
        with patch("registrar.models.domain.Domain.addRegistrant") as update_mock:
            call_command("update_missing_registrant_contacts", dry_run=False)
            self.assertEqual(
                PublicContact.objects.filter(contact_type=PublicContact.ContactTypeChoices.ADMINISTRATIVE).count(), 2
            )
            self.assertEqual(update_mock.call_count, 2)
