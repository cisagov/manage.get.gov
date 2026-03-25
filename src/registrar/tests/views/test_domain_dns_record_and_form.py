from unittest.mock import patch

from django.urls import reverse
from django_webtest import WebTest  # type: ignore
from waffle.testutils import override_flag

from registrar.utility.enums import DNSRecordTypes
from registrar.utility.errors import APIError
from registrar.tests.helpers.dns_data_generator import create_initial_dns_setup, create_dns_record, delete_all_dns_data

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
                    # User visible success message snippet
                    self.assertContains(response, f'{data["type"]} record for {data["name"]}')

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
        invalid_content_by_type = {"A": "not-an-ip", "AAAA": "not-an-ip", "TXT": 'not"valid text'}

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
        invalid_name = "testing!"
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
                    self.assertContains(
                        response, "Enter a name using only letters, numbers, hyphens, periods, or the @ symbol."
                    )

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
            self.assertContains(response, f'{record_case["type"]} comment for {record_case["name"]}')
