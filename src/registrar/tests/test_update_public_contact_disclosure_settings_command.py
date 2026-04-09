import os
from tempfile import TemporaryDirectory
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

    def _create_domain_with_registrant_contact(self, domain_name):
        domain = Domain.objects.create(name=domain_name)
        DomainInformation.objects.create(
            requester=self.user,
            domain=domain,
            organization_name="Cybersecurity and Infrastructure Security Agency",
            address_line1="1110 N. Glebe Rd",
            city="Arlington",
            state_territory="VA",
            zipcode="22201",
        )

        contact = PublicContact(
            contact_type=PublicContact.ContactTypeChoices.REGISTRANT,
            name=self.contact.name,
            org=self.contact.org,
            street1=self.contact.street1,
            city=self.contact.city,
            sp=self.contact.sp,
            pc=self.contact.pc,
            cc=self.contact.cc,
            email=self.contact.email,
            voice=self.contact.voice,
            pw=self.contact.pw,
        )
        contact.registry_id = "regContact"
        contact.domain = domain
        contact.save(skip_epp_save=True)

        return domain

    def _create_public_contact(self, domain, contact_type, registry_id, email=None):
        contact = PublicContact(
            contact_type=contact_type,
            name=self.contact.name,
            org=self.contact.org,
            street1=self.contact.street1,
            city=self.contact.city,
            sp=self.contact.sp,
            pc=self.contact.pc,
            cc=self.contact.cc,
            email=email or self.contact.email,
            voice=self.contact.voice,
            pw=self.contact.pw,
        )
        contact.registry_id = registry_id
        contact.domain = domain
        contact.save(skip_epp_save=True)
        return contact

    def test_dry_run_does_not_update_registry(self):
        with less_console_noise(), patch("registrar.models.domain.Domain._update_epp_contact") as update_mock:
            call_command(
                "update_public_contact_disclosure_settings",
                target_domain=self.domain.name,
                dry_run=True,
                contact_type=PublicContact.ContactTypeChoices.REGISTRANT,
            )

        update_mock.assert_not_called()

    def test_no_filters_runs_all_domains_and_contact_types(self):
        second_domain = self._create_domain_with_registrant_contact("second-example.gov")
        self._create_public_contact(
            domain=self.domain,
            contact_type=PublicContact.ContactTypeChoices.ADMINISTRATIVE,
            registry_id="adminContact",
        )
        self._create_public_contact(
            domain=self.domain,
            contact_type=PublicContact.ContactTypeChoices.SECURITY,
            registry_id="securityContact",
            email="security@example.gov",
        )
        self._create_public_contact(
            domain=self.domain,
            contact_type=PublicContact.ContactTypeChoices.TECHNICAL,
            registry_id="technicalContact",
        )

        processed_contacts = []

        def record_processed_contact(_command, dry_run, contact):
            processed_contacts.append((contact.domain.name, contact.contact_type, dry_run))
            return 0

        with patch(
            "registrar.management.commands.update_public_contact_disclosure_settings.Command._do_update",
            autospec=True,
            side_effect=record_processed_contact,
        ):
            with less_console_noise():
                call_command(
                    "update_public_contact_disclosure_settings",
                )

        self.assertEqual(
            processed_contacts,
            [
                (self.domain.name, PublicContact.ContactTypeChoices.REGISTRANT, True),
                (self.domain.name, PublicContact.ContactTypeChoices.ADMINISTRATIVE, True),
                (self.domain.name, PublicContact.ContactTypeChoices.SECURITY, True),
                (self.domain.name, PublicContact.ContactTypeChoices.TECHNICAL, True),
                (second_domain.name, PublicContact.ContactTypeChoices.REGISTRANT, True),
            ],
        )

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

    @patch(
        "registrar.management.commands.utility.terminal_helper.TerminalHelper.prompt_for_execution", return_value=True
    )
    def test_recovery_log_skips_domains_marked_done(self, _mock_prompt):
        failed_domain = self._create_domain_with_registrant_contact("middle-example.gov")
        trailing_domain = self._create_domain_with_registrant_contact("zulu-example.gov")

        attempted_domains = []
        failed_domains = []

        def fail_once(domain_self, contact):
            attempted_domains.append(domain_self.name)
            if domain_self.name == failed_domain.name and domain_self.name not in failed_domains:
                failed_domains.append(domain_self.name)
                raise RuntimeError("simulated update failure")

        with TemporaryDirectory() as temp_dir:
            recovery_log = os.path.join(temp_dir, "update_public_contacts_recovery_log.txt")

            with patch(
                "registrar.management.commands.update_public_contact_disclosure_settings.Command.RECOVERY_LOGFILE",
                recovery_log,
            ):
                with patch("registrar.models.domain.Domain._update_epp_contact", autospec=True, side_effect=fail_once):
                    with less_console_noise():
                        call_command(
                            "update_public_contact_disclosure_settings",
                            dry_run=False,
                            contact_type=PublicContact.ContactTypeChoices.REGISTRANT,
                        )

                    self.assertEqual(
                        attempted_domains,
                        [self.domain.name, failed_domain.name, trailing_domain.name],
                    )
                    with open(recovery_log, "r") as logfile:
                        recovery_log_lines = logfile.read().splitlines()
                    self.assertEqual(
                        recovery_log_lines,
                        [
                            f"{self.domain.name},done",
                            f"{failed_domain.name},error",
                            f"{trailing_domain.name},done",
                        ],
                    )

                    attempted_domains.clear()

                    with less_console_noise():
                        call_command(
                            "update_public_contact_disclosure_settings",
                            dry_run=False,
                            contact_type=PublicContact.ContactTypeChoices.REGISTRANT,
                            use_recovery_log=True,
                        )

                    self.assertEqual(attempted_domains, [failed_domain.name])
                    with open(recovery_log, "r") as logfile:
                        recovery_log_lines = logfile.read().splitlines()
                    self.assertEqual(
                        recovery_log_lines,
                        [
                            f"{self.domain.name},done",
                            f"{failed_domain.name},done",
                            f"{trailing_domain.name},done",
                        ],
                    )
