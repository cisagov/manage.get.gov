from unittest.mock import patch

from django.urls import reverse
from django_webtest import WebTest  # type: ignore
from waffle.testutils import override_flag

from registrar.utility.enums import DNSRecordTypes
from registrar.utility.errors import APIError
from registrar.tests.helpers.dns_data_generator import create_initial_dns_setup, create_dns_record, delete_all_dns_data
from registrar.validations import DNS_NAME_FORMAT_ERROR_MESSAGE

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
        self.assertContains(page, "<h2>Add record</h2>")

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_post_valid_forms_create_dns_records_success(self):
        for data in self.RECORD_TEST_CASES:
            with self.subTest(record_type=data["type"]):
                with patch("registrar.views.domain.DnsHostService") as MockSvc:
                    svc = MockSvc.return_value
                    svc.get_x_zone_id_if_zone_exists.return_value = ("zone-123", ["ex1.dns.gov"])
                    dns_record = create_dns_record(
                        self.dns_zone,
                        record_name=data["name"],
                        record_type=data["type"],
                        record_content=data["content"],
                        ttl=data["ttl"],
                    )
                    svc.create_dns_record.return_value = dns_record

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
