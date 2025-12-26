from unittest.mock import patch

from django.urls import reverse
from django_webtest import WebTest  # type: ignore
from waffle.testutils import override_flag
from django.conf import settings
from django.db.utils import OperationalError

from registrar.models import Domain, DomainInformation, UserDomainRole

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
        try:
            UserDomainRole.objects.all().delete()
            DomainInformation.objects.all().delete()
            Domain.objects.all().delete()
        except OperationalError:
            pass
        super().tearDown()


class TestDomainDNSRecordsView(TestWithDNSRecordPermissions, WebTest):
    def _url(self):
        return reverse("domain-dns-records", kwargs={"domain_pk": self.domain.id})

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_get_renders_page_and_form_fields_success(self):
        page = self.app.get(self._url(), status=200)

        # Are there other assertions that would work better here? I can get rid of this if the subsequent is sufficient
        self.assertIn("Records", page.text)
        self.assertIn("Add record", page.text)

        record_form = page.forms[0]

        # Assert required fields exist by name
        for field in ("type_field", "name", "content", "ttl", "comment"):
            self.assertIn(field, record_form.fields)

        # Defaults check
        self.assertEqual(str(record_form["ttl"].value), "300")
        self.assertEqual(record_form["type_field"].value, "A")

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_post_valid_form_creates_record_success(self):
        mock_record = {
            "id": "test1",
            "name": "www",
            "type": "A",
            "content": "192.0.2.10",
            "ttl": 300,
            "comment": "Mocked record created",
        }

        with patch("registrar.views.domain.DnsHostService") as MockSvc:
            svc = MockSvc.return_value
            svc.dns_setup.return_value = ["rainbow.dns.gov", "rainbow2.dns.gov"]
            svc.register_nameservers.return_value = None
            svc.get_x_zone_id_if_zone_exists.return_value = ("zone-123", True)
            svc.create_and_save_record.return_value = {"result": mock_record}

            page = self.app.get(self._url(), status=200)
            record_form = page.forms[0]

            record_form["type_field"] = "A"
            record_form["name"] = "www"
            record_form["content"] = "192.0.2.10"
            record_form["ttl"] = "300"
            record_form["comment"] = "hello"

            session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
            self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
            response = record_form.submit().follow()
            self.assertEqual(response.status_code, 200)

            # Service calls (behavioral assertions, as validation)
            svc.dns_setup.assert_called_once_with(self.domain.name)

            # User visible result
            self.assertIn("www", response.text)

    @override_flag("dns_hosting", active=True)
    @less_console_noise_decorator
    def test_post_invalid_form_throws_error(self):
        with patch("registrar.views.domain.DnsHostService") as MockSvc:
            svc = MockSvc.return_value

            page = self.app.get(self._url(), status=200)
            record_form = page.forms[0]

            record_form["type_field"] = "A"
            record_form["name"] = ""
            record_form["content"] = "not-an-ip"

            session_id = self.app.cookies[settings.SESSION_COOKIE_NAME]
            self.app.set_cookie(settings.SESSION_COOKIE_NAME, session_id)
            response = record_form.submit()

            # Invalid form should re-render the page, not redirect
            self.assertEqual(response.status_code, 200)

            # Service calls should not run
            svc.dns_setup.assert_not_called()

            self.assertIn("Name", response.text)
            self.assertIn("IPv4 Address", response.text)
