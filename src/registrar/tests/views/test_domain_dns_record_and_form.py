from unittest.mock import patch

from django.urls import reverse
from django_webtest import WebTest  # type: ignore
from waffle.testutils import override_flag

from registrar.models import DnsRecord
from registrar.utility.enums import DNSRecordTypes
from registrar.utility.errors import APIError
from registrar.tests.helpers.dns_data_generator import create_initial_dns_setup, create_dns_record, delete_all_dns_data
from registrar.validations import (
    CNAME_NAME_INLINE_ERROR_MESSAGE,
    CNAME_NAME_TARGET_BANNER_ERROR_MESSAGE,
    CNAME_TARGET_INLINE_ERROR_MESSAGE,
    DNS_NAME_FORMAT_ERROR_MESSAGE,
    DNS_RECORD_NAME_CONFLICT_ERROR_MESSAGE,
    DNS_RECORD_PRIORITY_REQUIRED_ERROR_MESSAGE,
)

from registrar.tests.test_views import TestWithUser
from api.tests.common import less_console_noise_decorator


class TestWithDNSRecordPermissions(TestWithUser):
    @less_console_noise_decorator
    def setUp(self):
        super().setUp()

        # Required by @grant_access(IS_STAFF)
        self.user.is_staff = True
        self.user.save()

        self.domain, self.dns_account, self.dns_zone = create_initial_dns_setup()

        self.client.force_login(self.user)

    def tearDown(self):
        delete_all_dns_data()
        super().tearDown()


class TestDomainDNSRecordsView(TestWithDNSRecordPermissions, WebTest):
    RECORD_TEST_CASES = [
        {
            "id": "test1",
            "name": "www",
            "type": "A",
            "content": "192.0.2.10",
            "ttl": 300,
            "comment": "Mocked record created",
        },
        {
            "id": "test1",
            "name": "www",
            "type": "AAAA",
            "content": "2001:db8::1",
            "ttl": 300,
            "comment": "Mocked record created",
        },
        # TODO: Uncomment test case after CNAME content validations finalized
        # {
        #     "id": "test-cname",
        #     "name": "www",
        #     "type": "CNAME",
        #     "content": "www.example.com",
        #     "ttl": 300,
        #     "comment": "Mocked record created",
        # },
        # TODO: Uncomment test case after PTR content validations finalized
        # {
        #     "id": "test-ptr",
        #     "name": "www",
        #     "type": "PTR",
        #     "content": "www.example.com",
        #     "ttl": 300,
        #     "comment": "Mocked record created",
        # },
        {
            "id": "test1",
            "name": "www",
            "type": "TXT",
            "content": "test record info",
            "ttl": 300,
            "comment": "Mocked record created",
        },
    ]

    def _url(self):
        return reverse("domain-dns-records", kwargs={"domain_pk": self.domain.id})

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_get_renders_page_success(self):
        page = self.client.get(self._url())
        # Assert we are on the correct page
        self.assertContains(page, "Add record</h3>")

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_post_valid_forms_create_dns_records_success(self):
        for data in self.RECORD_TEST_CASES:
            with self.subTest(record_type=data["type"]):
                with patch("registrar.views.domain.DnsHostService") as MockSvc:
                    svc = MockSvc.return_value
                    svc.get_x_zone_id_if_zone_exists.return_value = ("zone-123", ["ex1.dns.gov"])

                    # Create the DnsRecord row inside the mocked service call, not before the POST.
                    # Otherwise the new duplicate-record validator flags the POST as a dup of the
                    # pre-created row (since it has identical type/name/content).
                    def _create_and_return(*_args, _data=data, **_kwargs):
                        return create_dns_record(
                            self.dns_zone,
                            record_name=_data["name"],
                            record_type=_data["type"],
                            record_content=_data["content"],
                            ttl=_data["ttl"],
                            x_record_id=f"x-create-{_data['type']}",
                        )

                    svc.create_dns_record.side_effect = _create_and_return

                    response = self.client.post(
                        self._url(),
                        {
                            "type": data["type"],
                            "name": data["name"],
                            "ttl": data["ttl"],
                            "comment": data["comment"],
                            "content": data["content"],
                        },
                    )

                    self.assertEqual(response.status_code, 200)
                    messages = list(response.wsgi_request._messages)
                    self.assertEqual(str(messages[0]), "The DNS record for this domain has been added.")
                    self.assertRegex(
                        response.content.decode(),
                        r'<td id="dns-ttl-[^"]+"[^>]*>\s*5 minutes\s*</td>',
                    )

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_post_valid_form_api_error_returns_200_with_error_message(self):
        """Regression test for when create_and_save_record raises APIError after a valid
        form submission, the view must return 200 with an error message rather than crashing
        with TypeError from self.dns_record["form"] = ... when self.dns_record is None."""
        data = self.RECORD_TEST_CASES[0]

        with patch("registrar.views.domain.DnsHostService") as MockSvc:
            svc = MockSvc.return_value
            svc.get_x_zone_id_if_zone_exists.return_value = ("zone-123", ["ex1.dns.gov"])
            svc.create_dns_record.side_effect = APIError("Vendor rejected the record")

            response = self.client.post(
                self._url(),
                {
                    "type": data["type"],
                    "name": data["name"],
                    "ttl": data["ttl"],
                    "comment": data["comment"],
                    "content": data["content"],
                },
            )

            # Must not crash — previously raised TypeError: 'NoneType' object does not support item assignment
            self.assertEqual(response.status_code, 200)

            # Error path: only messagesRefresh triggered, not recordSubmitSuccess
            # (messages.error stores in session; HX-TRIGGER tells the frontend to fetch them)
            hx_trigger = response.headers.get("HX-TRIGGER", "")
            self.assertNotIn("recordSubmitSuccess", hx_trigger)

            # No new record row rendered because dns_record=None was passed to the template
            self.assertNotIn(f'{data["type"]} record for {data["name"]}', response)

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_post_invalid_content_throws_error(self):
        invalid_content_by_type = {
            "A": "not-an-ip",
            "AAAA": "not-an-ip",
            "TXT": 'not"valid text',
        }

        for record_case in self.RECORD_TEST_CASES:
            record_type = record_case["type"]
            with self.subTest(record_type=record_type):
                with patch("registrar.views.domain.DnsHostService"):
                    response = self.client.post(
                        self._url(),
                        {
                            "type": record_type,
                            "name": record_case["name"],
                            "ttl": record_case["ttl"],
                            "comment": record_case["comment"],
                            "content": invalid_content_by_type[record_type],
                        },
                    )

                    # Invalid form should re-render the page, not redirect
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, "Name")
                    self.assertContains(response, DNSRecordTypes(record_type).field_label)

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_post_invalid_dns_name_for_dns_record_throws_error(self):
        invalid_name = "testing("
        for record_case in self.RECORD_TEST_CASES:
            record_type = record_case["type"]
            with self.subTest(record_type=record_type):
                with patch("registrar.views.domain.DnsHostService"):
                    response = self.client.post(
                        self._url(),
                        {
                            "type": record_type,
                            "name": invalid_name,
                            "ttl": record_case["ttl"],
                            "comment": record_case["comment"],
                            "content": record_case["content"],
                        },
                    )

                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, DNS_NAME_FORMAT_ERROR_MESSAGE)

                    # Ensures appropriate label exists
                    self.assertContains(response, DNSRecordTypes(record_type).field_label)

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_get_txt_edit_form_uses_txt_partial(self):
        """TXT records in the edit form should render via txt_record_form.html,
        which contains the content-field-wrapper-txt marker."""
        create_dns_record(self.dns_zone, record_type="TXT", record_content="some text")

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "content-field-wrapper-txt")

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_get_dns_records_page_displays_comments(self):
        """
        If comments are on the record, they should be available in the dns records page
        """
        for record_case in self.RECORD_TEST_CASES:
            create_dns_record(
                self.dns_zone,
                record_type=record_case["type"],
                record_name=record_case["name"],
                record_content=record_case["content"],
                record_comment=record_case["comment"],
            )
        response = self.client.get(self._url())

        for record_case in self.RECORD_TEST_CASES:
            self.assertContains(response, f'Toggle to view comment for {record_case["name"]}')

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_get_dns_records_page_displays_human_readable_ttl(self):
        create_dns_record(self.dns_zone, ttl=300)

        response = self.client.get(self._url())

        self.assertContains(response, "5 minutes")
        self.assertNotContains(response, ">300<", html=False)

    # --- Tab order accessibility (issue #4804) ---
    # An open DNS record edit form must support a tab sequence of:
    #   Edit -> Name -> Content -> TTL -> Comment -> Cancel -> Save -> Delete
    #   -> More options -> next row's Edit
    # and the same sequence in reverse with Shift+Tab.
    # Focus reordering is implemented in JS (initDNSRecordTabOrder); these tests assert the
    # template-side hooks the JS depends on are present, so future refactors don't silently
    # break the accessibility contract.

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_dns_record_row_exposes_edit_button_hooks(self):
        """The Edit button must carry the data-action and data-record-id hooks the
        tab-order JS uses to identify the row."""
        record = create_dns_record(self.dns_zone)

        response = self.client.get(self._url())

        self.assertContains(response, 'data-action="edit"')
        self.assertContains(response, f'data-record-id="{record.id}"')

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_dns_record_row_exposes_kebab_with_aria_controls(self):
        """The 'More options' kebab must declare aria-controls so the tab-order JS can
        locate it per record."""
        record = create_dns_record(self.dns_zone)

        response = self.client.get(self._url())

        self.assertContains(response, f'aria-controls="more-actions-dnsrecord-{record.id}"')

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_dns_record_edit_form_delete_link_is_focusable(self):
        """The Delete control in the edit form is the 8th item in the tab sequence and
        must be reachable via keyboard. role=button + tabindex=0 makes it focusable;
        data-action='form-delete' lets the tab-order JS detect it as the last form pivot."""
        record = create_dns_record(self.dns_zone)

        response = self.client.get(self._url())
        content = response.content.decode()

        # All three markers must appear together on the form's Delete link.
        self.assertContains(response, 'aria-label="Delete DNS record from Cloudflare"')
        self.assertContains(response, 'data-action="form-delete"')
        self.assertContains(response, f'data-record-id="{record.id}"')
        self.assertIn('role="button"', content)
        self.assertIn('tabindex="0"', content)

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_dns_record_edit_form_cancel_button_has_focus_routing_hooks(self):
        """The Cancel button must carry data-action='form-cancel' so the tab-order JS can
        return focus to the Edit button when the form closes — otherwise focus is stranded
        inside the hidden form row and Tab walks past the kebab to the next record."""
        record = create_dns_record(self.dns_zone)

        response = self.client.get(self._url())

        self.assertContains(response, 'data-action="form-cancel"')
        self.assertContains(response, f'data-record-id="{record.id}"')

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_dns_record_edit_row_has_stable_id_for_focus_routing(self):
        """The edit form row id (dnsrecord-edit-row-<id>) is what the tab-order JS uses
        to find the open form's focusable controls."""
        record = create_dns_record(self.dns_zone)

        response = self.client.get(self._url())

        self.assertContains(response, f'id="dnsrecord-edit-row-{record.id}"')

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_dns_record_readonly_row_has_stable_id_for_focus_routing(self):
        """The readonly row id (dnsrecord-row-<id>) is what the tab-order JS uses
        to find the next record's Edit button when routing focus from the kebab."""
        record = create_dns_record(self.dns_zone)

        response = self.client.get(self._url())

        self.assertContains(response, f'id="dnsrecord-row-{record.id}"')

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_post_edit_unchanged_data_is_not_flagged_as_duplicate(self):
        """Editing a record and resubmitting without changes must not trip the
        full-duplicate validator. Regression: without binding the existing record
        as the form's instance, form.instance.pk is None and the validator fails
        to exclude the record being edited from its own uniqueness check.
        """
        existing = create_dns_record(
            self.dns_zone,
            record_type="A",
            record_name="www",
            record_content="192.0.2.10",
            ttl=300,
        )

        with patch("registrar.views.domain.DnsHostService") as MockSvc:
            svc = MockSvc.return_value
            svc.get_x_zone_id_if_zone_exists.return_value = ("zone-123", ["ex1.dns.gov"])
            svc.update_dns_record.return_value = existing

            response = self.client.post(
                self._url(),
                {
                    "id": existing.id,
                    "type": "A",
                    "name": "www",
                    "content": "192.0.2.10",
                    "ttl": 300,
                    "comment": "",
                },
            )

            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "You already entered this DNS record")
            svc.update_dns_record.assert_called_once()

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_post_edit_to_match_other_record_is_flagged_as_duplicate(self):
        """Editing a record so its fields collide with a DIFFERENT existing record
        must be flagged as a duplicate and must NOT call the vendor update."""
        # The record being edited
        editing = create_dns_record(
            self.dns_zone,
            record_type="A",
            record_name="mail",
            record_content="192.0.2.20",
            ttl=300,
            x_record_id="x-editing",
        )
        # Another record we're about to collide with
        create_dns_record(
            self.dns_zone,
            record_type="A",
            record_name="www",
            record_content="192.0.2.10",
            ttl=300,
            x_record_id="x-other",
        )

        with patch("registrar.views.domain.DnsHostService") as MockSvc:
            svc = MockSvc.return_value
            svc.get_x_zone_id_if_zone_exists.return_value = ("zone-123", ["ex1.dns.gov"])

            response = self.client.post(
                self._url(),
                {
                    "id": editing.id,
                    "type": "A",
                    "name": "www",
                    "content": "192.0.2.10",
                    "ttl": 300,
                    "comment": "",
                },
            )

            self.assertEqual(response.status_code, 200)
            svc.update_dns_record.assert_not_called()

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_post_cname_conflicts_with_existing_cname_flagged_inline(self):
        """Adding a CNAME when a CNAME with the same name already exists must surface
        an inline name-field error and must NOT call the vendor service."""
        create_dns_record(
            self.dns_zone,
            record_type="CNAME",
            record_name="www",
            record_content="cdn.example.com",
            ttl=300,
            x_record_id="x-existing-cname",
        )

        with patch("registrar.views.domain.DnsHostService") as MockSvc:
            svc = MockSvc.return_value
            svc.get_x_zone_id_if_zone_exists.return_value = ("zone-123", ["ex1.dns.gov"])

            response = self.client.post(
                self._url(),
                {
                    "type": "CNAME",
                    "name": "www",
                    "content": "cdn2.example.com",
                    "ttl": 300,
                    "comment": "",
                },
            )

            self.assertEqual(response.status_code, 200)
            self.assertContains(response, DNS_RECORD_NAME_CONFLICT_ERROR_MESSAGE)
            svc.create_dns_record.assert_not_called()

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_post_cname_conflicts_with_existing_a_record_flagged_inline(self):
        """Adding a CNAME when an A record with the same name exists must surface an
        inline error and must NOT call the vendor service."""
        create_dns_record(
            self.dns_zone,
            record_type="A",
            record_name="api",
            record_content="192.0.2.1",
            ttl=300,
            x_record_id="x-existing-a",
        )

        with patch("registrar.views.domain.DnsHostService") as MockSvc:
            svc = MockSvc.return_value
            svc.get_x_zone_id_if_zone_exists.return_value = ("zone-123", ["ex1.dns.gov"])

            response = self.client.post(
                self._url(),
                {
                    "type": "CNAME",
                    "name": "api",
                    "content": "cdn.example.com",
                    "ttl": 300,
                    "comment": "",
                },
            )

            self.assertEqual(response.status_code, 200)
            self.assertContains(response, DNS_RECORD_NAME_CONFLICT_ERROR_MESSAGE)
            svc.create_dns_record.assert_not_called()

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_post_duplicate_mx_record_at_root_flagged_inline(self):
        """Creating a duplicate MX record at the zone root must surface an inline error
        (priority must be stored correctly so the duplicate check can match it)."""
        DnsRecord.objects.create(
            dns_zone=self.dns_zone,
            type=DNSRecordTypes.MX,
            name="@",
            content="mail.example.gov",
            ttl=300,
            priority=1,
        )

        with patch("registrar.views.domain.DnsHostService") as MockSvc:
            svc = MockSvc.return_value
            svc.get_x_zone_id_if_zone_exists.return_value = ("zone-123", ["ex1.dns.gov"])

            response = self.client.post(
                self._url(),
                {
                    "type": "MX",
                    "name": "@",
                    "content": "mail.example.gov",
                    "priority": 1,
                    "ttl": 300,
                    "comment": "",
                },
            )

            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "You already entered this DNS record")
            svc.create_dns_record.assert_not_called()

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_post_duplicate_mx_record_using_zone_name_instead_of_at_flagged(self):
        """Submitting an MX record using the full zone name is treated as equivalent to '@'."""
        DnsRecord.objects.create(
            dns_zone=self.dns_zone,
            type=DNSRecordTypes.MX,
            name="@",
            content="mail.example.gov",
            ttl=300,
            priority=1,
        )

        with patch("registrar.views.domain.DnsHostService") as MockSvc:
            svc = MockSvc.return_value
            svc.get_x_zone_id_if_zone_exists.return_value = ("zone-123", ["ex1.dns.gov"])

            # Submit with full domain name instead of @
            response = self.client.post(
                self._url(),
                {
                    "type": "MX",
                    "name": self.domain.name,
                    "content": "mail.example.gov",
                    "priority": 1,
                    "ttl": 300,
                    "comment": "",
                },
            )

            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "You already entered this DNS record")
            svc.create_dns_record.assert_not_called()

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_post_duplicate_mx_shows_only_duplicate_error_on_priority_not_required_error(self):
        """A duplicate MX submission must show the duplicate message on priority but
        must NOT show the 'Enter a priority for this record.' required message.
        The two errors were co-appearing because add_error() removed priority from
        cleaned_data, causing _post_clean to skip setting instance.priority, which
        left it as None and triggered the model-level required check a second time."""
        DnsRecord.objects.create(
            dns_zone=self.dns_zone,
            type=DNSRecordTypes.MX,
            name="@",
            content="mail.example.gov",
            ttl=300,
            priority=1,
        )

        with patch("registrar.views.domain.DnsHostService") as MockSvc:
            svc = MockSvc.return_value
            svc.get_x_zone_id_if_zone_exists.return_value = ("zone-123", ["ex1.dns.gov"])

            response = self.client.post(
                self._url(),
                {
                    "type": "MX",
                    "name": "@",
                    "content": "mail.example.gov",
                    "priority": 1,
                    "ttl": 300,
                    "comment": "",
                },
            )

            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "You already entered this DNS record")
            self.assertNotContains(response, DNS_RECORD_PRIORITY_REQUIRED_ERROR_MESSAGE)
            svc.create_dns_record.assert_not_called()

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_post_cname_self_reference_shows_single_banner_with_inline_errors(self):
        """A CNAME pointing at itself should show a single banner message and two
        distinct inline messages (per ticket #4825).

        Top banner queues exactly one message: the banner text. The name and target
        fields each render their own inline error in the response body.
        """
        with patch("registrar.views.domain.DnsHostService") as MockSvc:
            svc = MockSvc.return_value
            svc.get_x_zone_id_if_zone_exists.return_value = ("zone-123", ["ex1.dns.gov"])

            response = self.client.post(
                self._url(),
                {
                    "type": "CNAME",
                    "name": "www",
                    "content": "www.example.gov",
                    "ttl": 300,
                    "comment": "",
                },
            )

            self.assertEqual(response.status_code, 200)
            svc.create_dns_record.assert_not_called()

            # Banner: a single message, matching the banner text
            queued = [str(m) for m in list(response.wsgi_request._messages)]
            self.assertEqual(queued, [CNAME_NAME_TARGET_BANNER_ERROR_MESSAGE])

            # Inline errors are attached to the form's name and content fields, but the
            # inline texts must NOT appear in the queued messages (otherwise the user
            # would see them stacked as banner alerts).
            form = response.context["form"]
            self.assertIn(CNAME_NAME_INLINE_ERROR_MESSAGE, form.errors.get("name", []))
            self.assertIn(CNAME_TARGET_INLINE_ERROR_MESSAGE, form.errors.get("content", []))
            self.assertNotIn(CNAME_NAME_INLINE_ERROR_MESSAGE, queued)
            self.assertNotIn(CNAME_TARGET_INLINE_ERROR_MESSAGE, queued)

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_post_field_only_error_still_shows_field_message_as_banner(self):
        """Regression test for the banner fallback path. When the form has no banner-level
        error, each unique field error is still queued as a banner message — preserving
        the existing UX for content/name shape errors and similar single-field validations.
        """
        with patch("registrar.views.domain.DnsHostService") as MockSvc:
            svc = MockSvc.return_value
            svc.get_x_zone_id_if_zone_exists.return_value = ("zone-123", ["ex1.dns.gov"])

            response = self.client.post(
                self._url(),
                {
                    "type": "A",
                    "name": "www",
                    "content": "not-an-ip",
                    "ttl": 300,
                    "comment": "",
                },
            )

            self.assertEqual(response.status_code, 200)
            svc.create_dns_record.assert_not_called()

            queued = [str(m) for m in list(response.wsgi_request._messages)]
            self.assertTrue(queued, "Expected at least one banner message for a field-only error")
