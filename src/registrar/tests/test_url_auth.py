"""Test that almost all URLs require authentication.

This uses deep Django URLConf pattern magic and was shamelessly lifted from
https://github.com/18F/tock/blob/main/tock/tock/tests/test_url_auth.py
"""

from django.test import TestCase
from django.urls import reverse, URLPattern
from django.urls.resolvers import URLResolver

import registrar.config.urls

from .common import less_console_noise

# When a URLconf pattern contains named capture groups, we'll use this
# dictionary to retrieve a sample value for it, which will be included
# in the sample URLs we generate, when attempting to perform a GET
# request on the view.
SAMPLE_KWARGS = {
    "app_label": "registrar",
    "domain_pk": "1",
    "domain_request_pk": "1",
    "domain_invitation_pk": "1",
    "pk": "1",
    "id": "1",
    "content_type_id": "2",
    "object_id": "3",
    "domain": "whitehouse.gov",
    "user_pk": "1",
    "portfolio_id": "1",
    "user_id": "1",
    "member_pk": "1",
    "invitedmember_pk": "1",
}

# Our test suite will ignore some namespaces.
IGNORE_NAMESPACES = [
    # The Django Debug Toolbar (DJDT) ends up in the URL config but it's always
    # disabled in production, so don't worry about it.
    "djdt"
]

# In general, we don't want to have any unnamed views, because that makes it
# impossible to generate sample URLs that point at them. We'll make exceptions
# for some namespaces that we don't have control over, though.
NAMESPACES_WITH_UNNAMED_VIEWS = ["admin", None]


def iter_patterns(urlconf, patterns=None, namespace=None):
    """
    Iterate through all patterns in the given Django URLconf.  Yields
    `(viewname, route)` tuples, where `viewname` is the fully-qualified view name
    (including its namespace, if any), and `route` is a regular expression that
    corresponds to the part of the pattern that contains any capturing groups.
    """
    if patterns is None:
        patterns = urlconf.urlpatterns
    for pattern in patterns:
        # Resolve if it's a route or an include
        if isinstance(pattern, URLPattern):
            viewname = pattern.name
            if viewname is None and namespace not in NAMESPACES_WITH_UNNAMED_VIEWS:
                raise AssertionError(f"namespace {namespace} cannot contain unnamed views")
            if namespace and viewname is not None:
                viewname = f"{namespace}:{viewname}"
            yield (viewname, pattern.pattern)
        elif isinstance(pattern, URLResolver):
            if len(pattern.default_kwargs.keys()) > 0:
                raise AssertionError("resolvers are not expected to have kwargs")
            if pattern.namespace and namespace is not None:
                raise AssertionError("nested namespaces are not currently supported")
            if pattern.namespace in IGNORE_NAMESPACES:
                continue
            yield from iter_patterns(urlconf, pattern.url_patterns, namespace or pattern.namespace)
        else:
            raise AssertionError("unknown pattern class")


def iter_sample_urls(urlconf):
    """
    Yields sample URLs for all entries in the given Django URLconf.
    This gets pretty deep into the muck of RoutePattern
    https://docs.djangoproject.com/en/2.1/_modules/django/urls/resolvers/
    """

    for viewname, route in iter_patterns(urlconf):
        if not viewname:
            continue
        if viewname == "auth_user_password_change":
            break
        named_groups = route.regex.groupindex.keys()
        kwargs = {}
        args = ()

        for kwarg in named_groups:
            if kwarg not in SAMPLE_KWARGS:
                raise AssertionError(f'Sample value for {kwarg} in pattern "{route}" not found')
            kwargs[kwarg] = SAMPLE_KWARGS[kwarg]

        url = reverse(viewname, args=args, kwargs=kwargs)
        yield (viewname, url)


class TestURLAuth(TestCase):
    """
    Tests to ensure that most URLs in a Django URLconf are protected by
    authentication.
    """

    # We won't test that the following URLs are protected by auth.
    # Note that the trailing slash is wobbly depending on how the URL was defined.
    IGNORE_URLS = [
        # These are the OIDC auth endpoints that always need
        # to be public. Use the exact URLs that will be tested.
        "/openid/login/",
        "/openid/logout/",
        "/openid/callback",
        "/openid/callback/login/",
        "/openid/callback/logout/",
        "/api/v1/available/",
        "/api/v1/get-report/current-federal",
        "/api/v1/get-report/current-full",
        "/api/v1/rdap/",
        "/health",
        "/version"
    ]

    # We will test that the following URLs are not protected by auth
    # and that the url returns a 200 response
    NO_AUTH_URLS = [
        "/health",
    ]

    def assertURLIsProtectedByAuth(self, url):
        """
        Make a GET request to the given URL, and ensure that it either redirects
        to login or denies access outright.
        """

        try:
            with less_console_noise():
                response = self.client.get(url)
        except Exception as e:
            # It'll be helpful to provide information on what URL was being
            # accessed at the time the exception occurred.  Python 3 will
            # also include a full traceback of the original exception, so
            # we don't need to worry about hiding the original cause.
            raise AssertionError(f'Accessing {url} raised "{e}"', e)

        code = response.status_code
        if code == 302:
            redirect = response["location"]
            self.assertRegex(
                redirect,
                r"^\/openid\/login",
                f"GET {url} should redirect to login or deny access, but instead " f"it redirects to {redirect}",
            )
        elif code == 401 or code == 403:
            pass
        else:
            raise AssertionError(
                f"GET {url} returned HTTP {code}, but should redirect to login or deny access",
            )

    def assertURLIsNotProtectedByAuth(self, url):
        """
        Make a GET request to the given URL, and ensure that it returns 200.
        """

        try:
            with less_console_noise():
                response = self.client.get(url)
        except Exception as e:
            # It'll be helpful to provide information on what URL was being
            # accessed at the time the exception occurred.  Python 3 will
            # also include a full traceback of the original exception, so
            # we don't need to worry about hiding the original cause.
            raise AssertionError(f'Accessing {url} raised "{e}"', e)

        code = response.status_code
        if code != 200:
            raise AssertionError(
                f"GET {url} returned HTTP {code}, but should return 200 OK",
            )

    def test_login_required_all_urls(self):
        """All URLs redirect to the login view."""
        for viewname, url in iter_sample_urls(registrar.config.urls):
            if url not in self.IGNORE_URLS:
                with self.subTest(viewname=viewname):
                    self.assertURLIsProtectedByAuth(url)
            elif url in self.NO_AUTH_URLS:
                with self.subTest(viewname=viewname):
                    self.assertURLIsNotProtectedByAuth(url)
