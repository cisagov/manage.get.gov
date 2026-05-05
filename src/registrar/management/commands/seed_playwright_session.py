"""Set up the user, domain, DNS records, and login session that the
Playwright UI tests need. Idempotent — reuses existing rows on re-runs.

Outputs eval-friendly key=value lines:
    SESSION_KEY=...
    DOMAIN_ID=...
    RECORD_IDS=...,...
plus a single PLAYWRIGHT_SEED_JSON= line for non-shell consumers.
"""

import json

from django.contrib.auth import SESSION_KEY, BACKEND_SESSION_KEY, HASH_SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore
from django.core.management.base import BaseCommand
from registrar.models import Domain, DomainInformation, User, UserDomainRole, WaffleFlag
from registrar.tests.helpers.dns_data_generator import (
    create_dns_record,
    create_initial_dns_setup,
)

# Recognizable values so anyone looking at the database can tell at a glance
# what created these rows. Don't use real-looking names here.
TEST_USERNAME = "playwright-test-user"
TEST_EMAIL = "playwright@test.local"
TEST_DOMAIN_NAME = "playwright-test.gov"


class Command(BaseCommand):
    help = "Set up a Django session + DNS test data so Playwright can log in."

    def handle(self, *args, **options):
        user = self._ensure_user()
        domain, records = self._ensure_domain_with_dns(user)
        self._ensure_dns_hosting_flag()
        session_key = self._mint_session(user)

        # eval-friendly key=value lines + a JSON line for non-shell consumers.
        self.stdout.write(f"SESSION_KEY={session_key}\n")
        self.stdout.write(f"DOMAIN_ID={domain.id}\n")
        self.stdout.write(f"RECORD_IDS={','.join(str(r.id) for r in records)}\n")
        self.stdout.write(
            "PLAYWRIGHT_SEED_JSON="
            + json.dumps(
                {
                    "sessionKey": session_key,
                    "domainId": domain.id,
                    "recordIds": [r.id for r in records],
                }
            )
            + "\n"
        )

    def _ensure_user(self):
        # All four name/title/phone fields are required so the
        # CheckUserProfileMiddleware doesn't redirect us to /user-profile.
        # is_staff is required by @grant_access(IS_STAFF) on the DNS view.
        defaults = {
            "email": TEST_EMAIL,
            "first_name": "Playwright",
            "last_name": "Tester",
            "title": "Test Engineer",
            "phone": "+1-555-555-5555",
            "is_staff": True,
        }
        user, created = User.objects.get_or_create(
            username=TEST_USERNAME,
            defaults=defaults,
        )
        # If someone in the past created the user with missing fields, top them up.
        if not created:
            updates = {k: v for k, v in defaults.items() if getattr(user, k, None) != v}
            if updates:
                for k, v in updates.items():
                    setattr(user, k, v)
                user.save()
        return user

    def _ensure_domain_with_dns(self, user):
        """Make sure `user` has a domain with at least two DNS records."""
        domain = Domain.objects.filter(name=TEST_DOMAIN_NAME).first()
        if domain is None:
            domain, _, dns_zone = create_initial_dns_setup()
            domain.name = TEST_DOMAIN_NAME
            domain.save()
        else:
            dns_zone = getattr(domain, "dnszone", None)
            if dns_zone is None:
                _, _, dns_zone = create_initial_dns_setup(domain=domain)

        # The view's permission check needs DomainInformation + a manager role.
        DomainInformation.objects.get_or_create(domain=domain, defaults={"requester": user})
        UserDomainRole.objects.get_or_create(
            user=user,
            domain=domain,
            defaults={"role": UserDomainRole.Roles.MANAGER},
        )

        # Two records are needed — one test checks Tab from kebab → next row's Edit.
        records = list(dns_zone.records.all().order_by("id")[:2])
        while len(records) < 2:
            idx = len(records) + 1
            records.append(
                create_dns_record(
                    dns_zone,
                    record_name=f"www{idx}",
                    record_type="A",
                    record_content=f"192.0.2.{idx}",
                    x_record_id=f"x-playwright-{idx}",
                )
            )
        return domain, records

    def _ensure_dns_hosting_flag(self):
        # Gates the DNS records page. Set for everyone in dev.
        WaffleFlag.objects.update_or_create(
            name="dns_hosting",
            defaults={"everyone": True},
        )

    def _mint_session(self, user):
        """Create a DB-backed login session for `user` and return its key.

        Same three writes django.contrib.auth.login() makes; the running app
        reads the same django_session row when the browser sends the cookie.
        """
        session = SessionStore()
        session[SESSION_KEY] = str(user.pk)
        session[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
        session[HASH_SESSION_KEY] = user.get_session_auth_hash()
        session.save()
        return session.session_key
