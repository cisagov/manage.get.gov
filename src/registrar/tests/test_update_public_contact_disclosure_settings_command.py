from unittest.mock import patch, call

from django.core.management import call_command
from epplib.models import common

from registrar.models import Domain, DomainInformation
from registrar.models.public_contact import PublicContact
from registrar.utility.enums import DefaultEmail

from .common import MockEppLib, less_console_noise, create_user

from epplibwrapper import common as epp


class TestUpdatePublicContactDisclosureSettingsCommand(MockEppLib):
    def setUp(self):
        super().setUp()
        self.domain = Domain.objects.create(name="example.gov")
        self.user = create_user(username="testuser", email="testuser@example.gov")
        self.domain_info = DomainInformation.objects.create(
            requester=self.user,
            domain=self.domain,
            organization_name="Cybersecurity and Infrastructure Security Agency",
            address_line1="1110 N. Glebe Rd",
            city="Arlington",
            state_territory="VA",
            zipcode="22201",
        )

        self.contact = PublicContact(
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
        self.contact.registry_id = "regContact"
        self.contact.domain = self.domain
        self.contact.save(skip_epp_save=True)

        DF = common.DiscloseField
        self.mockRegistrantContact = self.InfoDomainWithContacts.dummyInfoContactResultData(
            id="regContact",
            email="help@get.gov",
        )
        self.mockRegistrantContact.disclose = epp.Disclose(
            flag=False, fields=set(), types={DF.CC: "loc", DF.CITY: "loc", DF.PC: "loc", DF.SP: "loc"}
        )

    def test_dry_run_does_not_update_registry(self):
        with less_console_noise(), patch("registrar.models.domain.Domain._update_epp_contact") as update_mock:
            call_command(
                "update_public_contact_disclosure_settings",
                target_domain=self.domain.name,
                dry_run=True,
                contact_type=PublicContact.ContactTypeChoices.REGISTRANT,
            )

        update_mock.assert_not_called()

    @patch(
        "registrar.management.commands.utility.terminal_helper.TerminalHelper.prompt_for_execution",
        return_value=True,
    )
    def test_no_dry_run_updates_registry(self, _mock_prompt):
        self.assertEqual(PublicContact.objects.count(), 1)
        self.assertEqual(PublicContact.objects.filter(domain=self.domain).count(), 1)
        self.assertEqual(PublicContact.objects.filter(domain__name__iexact=self.domain.name).count(), 1)
        with patch("registrar.models.domain.Domain._update_epp_contact") as update_mock:
            call_command(
                "update_public_contact_disclosure_settings",
                target_domain=self.domain.name,
                dry_run=False,
                contact_type=PublicContact.ContactTypeChoices.REGISTRANT,
            )

        update_mock.assert_called_once()

    @patch(
        "registrar.management.commands.utility.terminal_helper.TerminalHelper.prompt_for_execution", return_value=True
    )
    def test_command_sends_expected_registrant_update(self, _mock_prompt):
        with self.subTest(contact_type="registrant"):
            with less_console_noise() and self.subTest(contact_type="registrant"):
                call_command(
                    "update_public_contact_disclosure_settings",
                    target_domain=self.domain.name,
                    dry_run=False,
                    contact_type=PublicContact.ContactTypeChoices.REGISTRANT,
                )

            expected_update = self._convertPublicContactToEpp(self.contact, createContact=False)

            self.mockedSendFunction.assert_has_calls(
                [call(expected_update, cleaned=True)],
                any_order=True,
            )

        with self.subTest(contact_type="security_non_default_email"):
            security = self.domain.get_default_security_contact()
            # PublicContact.registry_id is constrained to max_length=16.
            security.registry_id = "regContact"
            security.email = "security@example.gov"

            security.save(skip_epp_save=True)

            with less_console_noise():
                call_command(
                    "update_public_contact_disclosure_settings",
                    target_domain=self.domain.name,
                    dry_run=False,
                    contact_type=PublicContact.ContactTypeChoices.SECURITY,
                )

            expected_update = self._convertPublicContactToEpp(security, createContact=False)

            self.mockedSendFunction.assert_has_calls(
                [call(expected_update, cleaned=True)],
                any_order=True,
            )

    @patch(
        "registrar.management.commands.utility.terminal_helper.TerminalHelper.prompt_for_execution", return_value=True
    )
    def test_format_disclose_security_default_email(self, _mockprompt):
        with self.subTest(contact_type="security_default_email"):
            security = self.domain.get_default_security_contact()
            # PublicContact.registry_id is constrained to max_length=16.
            security.registry_id = "regContact"

            security.save(skip_epp_save=True)

            with less_console_noise():
                call_command(
                    "update_public_contact_disclosure_settings",
                    target_domain=self.domain.name,
                    dry_run=False,
                    contact_type=PublicContact.ContactTypeChoices.SECURITY,
                )

            expected_update = self._convertPublicContactToEpp(security, createContact=False)

            self.mockedSendFunction.assert_has_calls(
                [call(expected_update, cleaned=True)],
                any_order=True,
            )
