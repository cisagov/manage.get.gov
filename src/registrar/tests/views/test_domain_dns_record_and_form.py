from unittest.mock import patch

from django.urls import reverse
from django_webtest import WebTest  # type: ignore
from waffle.testutils import override_flag
from django.conf import settings

from registrar.models import Domain, DomainInformation, UserDomainRole, DnsZone, DnsAccount
from registrar.forms.domain import DomainDNSRecordForm
from registrar.utility.enums import DNSRecordTypes

from registrar.tests.test_views import TestWithUser
from api.tests.common import less_console_noise_decorator


class TestWithDNSRecordPermissions(TestWithUser):
    @less_console_noise_decorator
    def setUp(self):
        super().setUp()

        # Required by @grant_access(IS_STAFF)
        self.user.is_staff = True
        self.user.save()

        self.domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        DomainInformation.objects.get_or_create(
            requester=self.user,
            domain=self.domain,
        )

        UserDomainRole.objects.get_or_create(
            user=self.user,
            domain=self.domain,
            role=UserDomainRole.Roles.MANAGER,
        )

        self.app.set_user(self.user.username)

    def tearDown(self):
        UserDomainRole.objects.all().delete()
        DomainInformation.objects.all().delete()
        Domain.objects.all().delete()
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

    def setUp(self):
        super().setUp()
        self.dns_domain, _ = Domain.objects.get_or_create(name="igorville.gov")
        self.dns_account = DnsAccount.objects.create(name="acct-base")
        self.dns_zone = DnsZone.objects.create(
            dns_account=self.dns_account, domain=self.dns_domain, nameservers=["ns1.dns-test.gov", "ns2.dns-test.gov"]
        )

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

    def valid_form_creates_record(self, params):
        mock_record = {
            "id": params["id"],
            "name": params["name"],
            "type": params["type"],
            "content": params["content"],
            "ttl": params["ttl"],
            "comment": params["comment"],
        }

        with patch("registrar.views.domain.DnsHostService") as MockSvc:
            svc = MockSvc.return_value
            svc.register_nameservers.return_value = None
            svc.get_x_zone_id_if_zone_exists.return_value = ("zone-123", True)
            svc.create_and_save_record.return_value = {"result": mock_record}

            page = self.app.get(self._url(), status=200)
            record_form = page.forms[0]

            record_form["type"] = params["type"]
            record_form["name"] = params["name"]
            record_form["content"] = params["content"]
            record_form["ttl"] = params["ttl"]
            record_form["comment"] = params["comment"]

            session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
            self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
            response = record_form.submit()
            self.assertEqual(response.status_code, 200)

            # User visible success message snippet
            self.assertIn(f'{params["type"]} record for {params["name"]}', response.text)

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_post_valid_a_form_creates_record_success(self):
        self.valid_form_creates_record(self.RECORD_TEST_CASES[0])

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_post_valid_aaaa_form_creates_record_success(self):
        self.valid_form_creates_record(self.RECORD_TEST_CASES[1])

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
