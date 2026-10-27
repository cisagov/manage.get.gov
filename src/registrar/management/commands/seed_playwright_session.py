"""Set up the user, domain, DNS records, and login session that the
Playwright UI tests need. Safe to re-run — reuses existing rows.

Outputs eval-friendly key=value lines:
    SESSION_KEY=...
plus a single PLAYWRIGHT_SEED_JSON= line for non-shell consumers.
"""

import json

from django.contrib.auth import SESSION_KEY, BACKEND_SESSION_KEY, HASH_SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore
from django.core.management.base import BaseCommand
from registrar.models import Domain, DomainInformation, User, UserDomainRole, WaffleFlag, UserGroup
from registrar.tests.helpers.dns_data_generator import (
    create_dns_record,
    create_initial_dns_setup,
)

# Recognizable values so anyone looking at the database can tell at a glance
# what created these rows. Don't use real-looking names here.
TEST_USERNAME = "playwright-test-user"
TEST_EMAIL = "playwright@test.local"


class Command(BaseCommand):
    help = "Set up a Django session + DNS test data so Playwright can log in."

    def handle(self, *args, **options):
        user = self._ensure_user()
        session_key = self._mint_session(user)

        # eval-friendly key=value lines + a JSON line for non-shell consumers.
        self.stdout.write(f"SESSION_KEY={session_key}\n")
        self.stdout.write(
            "PLAYWRIGHT_SEED_JSON="
            + json.dumps(
                {
                    "sessionKey": session_key,
                }
            )
            + "\n"
        )

    def _ensure_user(self):
        # All four name/title/phone fields are required so the
        # CheckUserProfileMiddleware doesn't redirect us to /user-profile.
        defaults = {
            "email": TEST_EMAIL,
            "first_name": "Playwright",
            "last_name": "Tester",
            "title": "Test Engineer",
            "phone": "+1-555-555-5555"
        }
        user, created = User.objects.get_or_create(
            username=TEST_USERNAME,
            defaults=defaults,
        )
        group = UserGroup.objects.get(name='full_access_group')

        group.user_set.add(user)
        # If someone in the past created the user with missing fields, top them up.
        if not created:
            updates = {k: v for k, v in defaults.items() if getattr(user, k, None) != v}
            if updates:
                for k, v in updates.items():
                    setattr(user, k, v)
                user.save()
        return user

    def _mint_session(self, user):
        """Create a DB-backed login session for `user` and return its key.

        Same three writes django.contrib.auth.login() makes; the running app
        reads the same django_session row when the browser sends the cookie.
        """
        session = SessionStore()
        session[SESSION_KEY] = str(user.pk)
        session[BACKEND_SESSION_KEY] = "djangooidc.backends.OpenIdConnectBackend"
        session[HASH_SESSION_KEY] = user.get_session_auth_hash()
        session.save()
        return session.session_key