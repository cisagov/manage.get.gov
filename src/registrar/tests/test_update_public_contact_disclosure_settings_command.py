from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from epplib.models import common

from registrar.management.commands.update_public_contact_disclosure_settings import (
    Command as UpdatePublicContactDisclosureSettingsCommand,
)
from registrar.models import Domain
from registrar.models.public_contact import PublicContact

from .common import less_console_noise


class TestUpdatePublicContactDisclosureSettingsCommand(TestCase):
    def setUp(self):
        self.domain = Domain.objects.create(name="example.gov")

        self.contact = PublicContact.get_default_registrant()
        self.contact.domain = self.domain
        self.contact.registry_id = "regContact123456"
        self.contact.save(skip_epp_save=True)

    def test_dry_run_does_not_update_registry(self):
        with less_console_noise(), patch("registrar.models.domain.Domain._update_epp_contact") as update_mock:
            call_command(
                "update_public_contact_disclosure_settings",
                target_domain=self.domain.name,
                dry_run=True,
            )

        update_mock.assert_not_called()

    @patch(
        "registrar.management.commands.utility.terminal_helper.TerminalHelper.prompt_for_execution",
        return_value=True,
    )
    def test_no_dry_run_updates_registry(self, _mock_prompt):
        with less_console_noise(), patch("registrar.models.domain.Domain._update_epp_contact") as update_mock:
            call_command(
                "update_public_contact_disclosure_settings",
                target_domain=self.domain.name,
                dry_run=False,
            )

        update_mock.assert_called_once()

    def test_format_disclose_includes_flag_and_overrides(self):
        cmd = UpdatePublicContactDisclosureSettingsCommand()
        DF = common.DiscloseField

        with self.subTest(contact_type="registrant"):
            disclose = self.domain._disclose_fields(contact=self.contact)
            self.assertEqual(
                cmd._format_disclose(disclose),
                "flag=T fields=[cc,city,org,sp] types=[cc:loc,city:loc,org:loc,sp:loc]",
            )

        with self.subTest(contact_type="security_non_default_email"):
            security = self.domain.get_default_security_contact()
            # PublicContact.registry_id is constrained to max_length=16.
            security.registry_id = "regIdentifa123456"
            security.email = "security@example.gov"

            security.save(skip_epp_save=True)

            disclose = self.domain._disclose_fields(contact=security)
            all_fields = {field for field in DF}
            expected_fields = all_fields - {DF.NOTIFY_EMAIL, DF.VAT, DF.IDENT, DF.EMAIL}
            expected_types = {DF.ADDR: "loc", DF.NAME: "loc"}

            expected_types_formatted = ",".join(
                sorted(f"{field.value}:{type_value}" for field, type_value in expected_types.items())
            )
            expected = (
                "flag=F "
                f"fields=[{','.join(sorted(field.value for field in expected_fields))}] "
                f"types=[{expected_types_formatted}]"
            )

            self.assertEqual(cmd._format_disclose(disclose), expected)
