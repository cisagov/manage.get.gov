from unittest.mock import patch

from django.urls import reverse
from django_webtest import WebTest  # type: ignore
from waffle.testutils import override_flag

from registrar.models import DnsRecord
from registrar.utility.enums import DNSRecordTypes
from registrar.utility.errors import APIError
from registrar.tests.helpers.dns_data_generator import create_initial_dns_setup, create_dns_record, delete_all_dns_data
from registrar.validations import DNS_NAME_FORMAT_ERROR_MESSAGE, DNS_RECORD_PRIORITY_REQUIRED_ERROR_MESSAGE

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
            self.assertContains(response, "A record with that name already exists")
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
            self.assertContains(response, "A record with that name already exists")
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
