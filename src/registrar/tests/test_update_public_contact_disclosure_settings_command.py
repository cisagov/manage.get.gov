from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from epplib.models import common

from registrar.management.commands.update_public_contact_disclosure_settings import (
    Command as UpdatePublicContactDisclosureSettingsCommand,
)
from registrar.models import Domain
from registrar.models.public_contact import PublicContact
from registrar.utility.enums import DefaultEmail

from .common import less_console_noise


class TestUpdatePublicContactDisclosureSettingsCommand(TestCase):
    def setUp(self):
        self.domain = Domain.objects.create(name="example.gov")

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
        self.contact.registry_id = "regContact123456"
        self.contact.domain = self.domain
        self.contact.save(skip_epp_save=True)

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

    def test_format_disclose_includes_flag_and_overrides(self):
        cmd = UpdatePublicContactDisclosureSettingsCommand()
        DF = common.DiscloseField

        with self.subTest(contact_type="registrant"):
            disclose = self.domain._disclose_fields(contact=self.contact)
            self.assertEqual(
                cmd._format_disclose(disclose),
                "flag=T "
                f"fields=[{DF.CC},{DF.CITY},{DF.ORG},{DF.SP}] "
                f"types=[{DF.ADDR}:loc,{DF.CC}:loc,{DF.CITY}:loc,{DF.NAME}:loc,"
                f"{DF.ORG}:loc,{DF.PC}:loc,{DF.SP}:loc,{DF.STREET}:loc]",
            )

        with self.subTest(contact_type="security_non_default_email"):
            security = self.domain.get_default_security_contact()
            # PublicContact.registry_id is constrained to max_length=16.
            security.registry_id = "regContact123456"
            security.email = "security@example.gov"

            security.save(skip_epp_save=True)

            disclose = self.domain._disclose_fields(contact=security)

            expected = (
                "flag=T "
                f"fields=[{DF.EMAIL}] "
                f"types=[{DF.ADDR}:loc,{DF.CC}:loc,{DF.CITY}:loc,{DF.NAME}:loc,"
                f"{DF.ORG}:loc,{DF.PC}:loc,{DF.SP}:loc,{DF.STREET}:loc]"
            )

            self.assertEqual(cmd._format_disclose(disclose), expected)

        with self.subTest(contact_type="security_default_email"):
            security = self.domain.get_default_security_contact()
            # PublicContact.registry_id is constrained to max_length=16.
            security.registry_id = "regContact789012"

            security.save(skip_epp_save=True)

            disclose = self.domain._disclose_fields(contact=security)

            expected = (
                "flag=T "
                f"fields=[] "
                f"types=[{DF.ADDR}:loc,{DF.CC}:loc,{DF.CITY}:loc,{DF.NAME}:loc,"
                f"{DF.ORG}:loc,{DF.PC}:loc,{DF.SP}:loc,{DF.STREET}:loc]"
            )

            self.assertEqual(cmd._format_disclose(disclose), expected)
