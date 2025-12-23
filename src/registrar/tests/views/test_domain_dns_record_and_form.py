from unittest.mock import patch

from django.urls import reverse
from django_webtest import WebTest  # type: ignore
from waffle.testutils import override_flag

from registrar.models import Domain, DomainInformation, UserDomainRole
from registrar.models.dns.dns_zone import DnsZone

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
        self.client.force_login(self.user)

    def tearDown(self):
        try:
            DnsZone.objects.all().delete()
            UserDomainRole.objects.all().delete()
            DomainInformation.objects.all().delete()
            Domain.objects.all().delete()
        except Exception:
            pass
        super().tearDown()


class TestDomainDNSRecordsView(TestWithDNSRecordPermissions, WebTest):
    def _url(self):
        return reverse("domain-dns-records", kwargs={"domain_pk": self.domain.id})

        @override_flag("dns_hosting", active=True)
        @less_console_noise_decorator
        def test_get_renders_page_and_form_fields(self):
            page = self.app.get(self._url(), status=200)

            self.assertIn("Records", page.text)
            self.assertIn("Add Record", page.text)

            # form exists, even if hidden by Alpine
            form = page.forms["form-container"]

            # Assert required fields exist by name
            for field in ("type_field", "name", "content", "ttl", "comment"):
                self.assertIn(field, form.fields)

            # Defaults check
            self.assertEqual(str(form["ttl"].value), "300")
            self.assertEqual(form["type_field"].value, "Select a type")
