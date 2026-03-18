from unittest.mock import patch

from django.urls import reverse
from django_webtest import WebTest  # type: ignore
from waffle.testutils import override_flag
from django.conf import settings

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

        self.app.set_user(self.user.username)

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
    ]

    def _url(self):
        return reverse("domain-dns-records", kwargs={"domain_pk": self.domain.id})

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_get_renders_page_and_form_fields_success(self):
        page = self.app.get(self._url(), status=200)

        # Assert we are on the correct page
        self.assertIn("Add record", page.text)

        record_form = page.forms[0]

        # Assert required fields for A type records exist by name
        for field in ("type", "name", "content", "ttl", "comment"):
            self.assertIn(field, record_form.fields)

        # Defaults check for A type records
        self.assertEqual(str(record_form["ttl"].value), "300")

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_post_valid_forms_create_records_success(self):
        for data in self.RECORD_TEST_CASES:
            with self.subTest(record_type=data["type"]):
                mock_record = {
                    "id": data["id"],
                    "name": data["name"],
                    "type": data["type"],
                    "content": data["content"],
                    "ttl": data["ttl"],
                    "comment": data["comment"],
                }

                with patch("registrar.views.domain.DnsHostService") as MockSvc:
                    svc = MockSvc.return_value
                    svc.register_nameservers.return_value = None
                    svc.get_x_zone_id_if_zone_exists.return_value = ("zone-123", True)
                    dns_record = create_dns_record(
                        self.dns_zone,
                        record_name=data["name"],
                        record_type=data["type"],
                        record_content=data["content"],
                        ttl=data["ttl"],
                    )
                    svc.create_and_save_record.return_value = {"result": mock_record, "dns_record": dns_record}

                    page = self.app.get(self._url(), status=200)
                    record_form = page.forms[0]

                    record_form["type"] = data["type"]
                    record_form["name"] = data["name"]
                    record_form["content"] = data["content"]
                    record_form["ttl"] = data["ttl"]
                    record_form["comment"] = data["comment"]

                    session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
                    self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
                    response = record_form.submit()
                    self.assertEqual(response.status_code, 200)

                    # User visible success message snippet
                    self.assertIn(f'{data["type"]} record for {data["name"]}', response.text)

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_post_valid_form_api_error_returns_200_with_error_message(self):
        """Regression test for when create_and_save_record raises APIError after a valid
        form submission, the view must return 200 with an error message rather than crashing
        with TypeError from self.dns_record["form"] = ... when self.dns_record is None."""
        data = self.RECORD_TEST_CASES[0]

        with patch("registrar.views.domain.DnsHostService") as MockSvc:
            svc = MockSvc.return_value
            svc.get_x_zone_id_if_zone_exists.return_value = ("zone-123", True)
            svc.create_and_save_record.side_effect = APIError("Vendor rejected the record")

            page = self.app.get(self._url(), status=200)
            record_form = page.forms[0]

            record_form["type"] = data["type"]
            record_form["name"] = data["name"]
            record_form["content"] = data["content"]
            record_form["ttl"] = data["ttl"]

            session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
            self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
            response = record_form.submit()

            # Must not crash — previously raised TypeError: 'NoneType' object does not support item assignment
            self.assertEqual(response.status_code, 200)

            # Error path: only messagesRefresh triggered, not recordSubmitSuccess
            # (messages.error stores in session; HX-TRIGGER tells the frontend to fetch them)
            hx_trigger = response.headers.get("HX-TRIGGER", "")
            self.assertNotIn("recordSubmitSuccess", hx_trigger)

            # No new record row rendered because dns_record=None was passed to the template
            self.assertNotIn(f'{data["type"]} record for {data["name"]}', response.text)

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_post_invalid_content_throws_error(self):
        invalid_content_by_type = {
            "A": "not-an-ip",
            "AAAA": "not-an-ip",
        }

        for record_case in self.RECORD_TEST_CASES:
            record_type = record_case["type"]
            with self.subTest(record_type=record_type):
                with patch("registrar.views.domain.DnsHostService"):
                    page = self.app.get(self._url(), status=200)
                    record_form = page.forms[0]

                    record_form["type"] = record_type
                    record_form["name"] = "@"
                    record_form["content"] = invalid_content_by_type[record_type]

                    session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
                    self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
                    response = record_form.submit()

                    # Invalid form should re-render the page, not redirect
                    self.assertEqual(response.status_code, 200)
                    self.assertIn("Name", response.text)
                    self.assertIn(DNSRecordTypes(record_type).error_message, response.text)

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_post_invalid_dns_name_for_dns_record_throws_error(self):
        for record_case in self.RECORD_TEST_CASES:
            record_type = record_case["type"]
            with self.subTest(record_type=record_type):
                with patch("registrar.views.domain.DnsHostService"):
                    page = self.app.get(self._url(), status=200)
                    record_form = page.forms[0]

                    record_form["type"] = record_type
                    record_form["name"] = "testing!"
                    record_form["content"] = record_case["content"]

                    session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
                    self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
                    response = record_form.submit()

                    self.assertEqual(response.status_code, 200)
                    self.assertIn(
                        "Enter a name using only letters, numbers, hyphens, periods, or the @ symbol.", response.text
                    )

                    # Ensures appropriate label exists
                    self.assertIn(DNSRecordTypes(record_type).field_label, response.text)
