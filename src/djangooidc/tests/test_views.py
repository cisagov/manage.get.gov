from unittest.mock import MagicMock, patch

from django.http import HttpResponse
from django.test import Client, TestCase, RequestFactory
from django.urls import reverse

from djangooidc.exceptions import NoStateDefined, InternalError
from ..views import login_callback, CLIENT

from .common import less_console_noise


@patch("djangooidc.views.CLIENT", new_callable=MagicMock)
class ViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()

    def say_hi(*args):
        return HttpResponse("Hi")

    def create_acr(*args):
        return "any string"

    def user_info(*args):
        return {
            "sub": "TEST",
            "email": "test@example.com",
            "first_name": "Testy",
            "last_name": "Tester",
            "phone": "814564000",
        }

    def test_error_page(self, mock_client):
        pass

    def test_openid_sets_next(self, mock_client):
        """ Test that the openid method properly sets next in the session."""
        with less_console_noise():
            # SETUP
            # set up the callback url that will be tested in assertions against
            # session[next]
            callback_url = reverse("openid_login_callback")
            # MOCK
            # when login is called, response from create_authn_request should
            # be returned to user, so let's mock it and test it
            mock_client.create_authn_request.side_effect = self.say_hi
            # in this case, we need to mock the get_default_acr_value so that
            # openid method will execute properly, but the acr_value itself
            # is not important for this test
            mock_client.get_default_acr_value.side_effect = self.create_acr
            # TEST
            # test the login url, passing a callback url
            response = self.client.get(reverse("login"), {"next": callback_url})
            # ASSERTIONS
            session = mock_client.create_authn_request.call_args[0][0]
            # assert the session[next] is set to the callback_url
            self.assertEqual(session["next"], callback_url)
            # assert that openid returned properly the response from
            # create_authn_request
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Hi")

    def test_openid_raises(self, mock_client):
        """Test that errors in openid raise 500 error for the user.
        This test specifically tests for any exceptions that might be raised from
        create_authn_request. This includes scenarios where CLIENT exists, but
        is no longer functioning properly."""
        with less_console_noise():
            # MOCK
            # when login is called, exception thrown from create_authn_request
            # should present 500 error page to user
            mock_client.create_authn_request.side_effect = Exception("Test")
            # TEST
            # test when login url is called
            response = self.client.get(reverse("login"))
            # ASSERTIONS
            # assert that the 500 error page is raised
            self.assertEqual(response.status_code, 500)
            self.assertTemplateUsed(response, "500.html")
            self.assertIn("Server error", response.content.decode("utf-8"))

    def test_openid_raises_when_client_is_none_and_cant_init(self, mock_client):
        """Test that errors in openid raise 500 error for the user.
        This test specifically tests for the condition where the CLIENT
        is None and the client initialization attempt raises an exception."""
        with less_console_noise():
            # MOCK
            # mock that CLIENT is None
            # mock that Client() raises an exception (by mocking _initialize_client)
            # Patch CLIENT to None for this specific test
            with patch("djangooidc.views.CLIENT", None):
                # Patch _initialize_client() to raise an exception
                with patch("djangooidc.views._initialize_client") as mock_init:
                    mock_init.side_effect = InternalError
                    # TEST
                    # test when login url is called
                    response = self.client.get(reverse("login"))
                    # ASSERTIONS
                    # assert that the 500 error page is raised
                    self.assertEqual(response.status_code, 500)
                    self.assertTemplateUsed(response, "500.html")
                    self.assertIn("Server error", response.content.decode("utf-8"))

    def test_openid_initializes_client_and_calls_create_authn_request(self, mock_client):
        """Test that openid re-initializes the client when the client had not
        been previously initiated."""
        with less_console_noise():
            # MOCK
            # response from create_authn_request should
            # be returned to user, so let's mock it and test it
            mock_client.create_authn_request.side_effect = self.say_hi
            # in this case, we need to mock the get_default_acr_value so that
            # openid method will execute properly, but the acr_value itself
            # is not important for this test
            mock_client.get_default_acr_value.side_effect = self.create_acr
            with patch("djangooidc.views._initialize_client") as mock_init_client:
                with patch("djangooidc.views._client_is_none") as mock_client_is_none:
                    # mock the client to initially be None
                    mock_client_is_none.return_value = True
                    # TEST
                    # test when login url is called
                    response = self.client.get(reverse("login"))
                    # ASSERTIONS
                    # assert that _initialize_client was called
                    mock_init_client.assert_called_once()
                    # assert that the response is the mocked response from create_authn_request
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, "Hi")

    def test_login_callback_with_no_session_state(self, mock_client):
        """If the local session is None (ie the server restarted while user was logged out),
        we do not throw an exception. Rather, we attempt to login again."""
        with less_console_noise():
            # MOCK
            # mock the acr_value to some string
            # mock the callback function to raise the NoStateDefined Exception
            mock_client.get_default_acr_value.side_effect = self.create_acr
            mock_client.callback.side_effect = NoStateDefined()
            # TEST
            # test the login callback
            response = self.client.get(reverse("openid_login_callback"))
            # ASSERTIONS
            # assert that the user is redirected to the start of the login process
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, "/")

    def test_login_callback_reads_next(self, mock_client):
        """If the next value is set in the session, test that login_callback returns
        a redirect to the 'next' url."""
        with less_console_noise():
            # SETUP
            session = self.client.session
            # set 'next' to the logout url
            session["next"] = reverse("logout")
            session.save()
            # MOCK
            # mock that callback returns user_info; this is the expected behavior
            mock_client.callback.side_effect = self.user_info
            # patch that the request does not require step up auth
            # TEST
            # test the login callback url
            with patch("djangooidc.views._requires_step_up_auth", return_value=False):
                response = self.client.get(reverse("openid_login_callback"))
            # ASSERTIONS
            # assert the redirect url is the same as the 'next' value set in session
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse("logout"))

    def test_login_callback_no_step_up_auth(self, mock_client):
        """Walk through login_callback when _requires_step_up_auth returns False
        and assert that we have a redirect to /"""
        with less_console_noise():
            # SETUP
            session = self.client.session
            session.save()
            # MOCK
            # mock that callback returns user_info; this is the expected behavior
            mock_client.callback.side_effect = self.user_info
            # patch that the request does not require step up auth
            # TEST
            # test the login callback url
            with patch("djangooidc.views._requires_step_up_auth", return_value=False):
                response = self.client.get(reverse("openid_login_callback"))
            # ASSERTIONS
            # assert that redirect is to / when no 'next' is set
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, "/")

    def test_requires_step_up_auth(self, mock_client):
        """Invoke login_callback passing it a request when _requires_step_up_auth returns True
        and assert that session is updated and create_authn_request (mock) is called."""
        with less_console_noise():
            # MOCK
            # Configure the mock to return an expected value for get_step_up_acr_value
            mock_client.return_value.get_step_up_acr_value.return_value = "step_up_acr_value"
            # Create a mock request
            request = self.factory.get("/some-url")
            request.session = {"acr_value": ""}
            # Ensure that the CLIENT instance used in login_callback is the mock
            # patch _requires_step_up_auth to return True
            with patch("djangooidc.views._requires_step_up_auth", return_value=True), patch(
                "djangooidc.views.CLIENT.create_authn_request", return_value=MagicMock()
            ) as mock_create_authn_request:
                # TEST
                # test the login callback
                login_callback(request)
            # ASSERTIONS
            # create_authn_request only gets called when _requires_step_up_auth is True
            # and it changes this acr_value in request.session
            # Assert that acr_value is no longer empty string
            self.assertNotEqual(request.session["acr_value"], "")
            # And create_authn_request was called again
            mock_create_authn_request.assert_called_once()

    def test_does_not_requires_step_up_auth(self, mock_client):
        """Invoke login_callback passing it a request when _requires_step_up_auth returns False
        and assert that session is not updated and create_authn_request (mock) is not called.

        Possibly redundant with test_login_callback_requires_step_up_auth"""
        with less_console_noise():
            # MOCK
            # Create a mock request
            request = self.factory.get("/some-url")
            request.session = {"acr_value": ""}
            # Ensure that the CLIENT instance used in login_callback is the mock
            # patch _requires_step_up_auth to return False
            with patch("djangooidc.views._requires_step_up_auth", return_value=False), patch(
                "djangooidc.views.CLIENT.create_authn_request", return_value=MagicMock()
            ) as mock_create_authn_request:
                # TEST
                # test the login callback
                login_callback(request)
            # ASSERTIONS
            # create_authn_request only gets called when _requires_step_up_auth is True
            # and it changes this acr_value in request.session
            # Assert that acr_value is NOT updated by testing that it is still an empty string
            self.assertEqual(request.session["acr_value"], "")
            # Assert create_authn_request was not called
            mock_create_authn_request.assert_not_called()

    @patch("djangooidc.views.authenticate")
    def test_login_callback_raises(self, mock_auth, mock_client):
        """Test that login callback raises a 401 when user is unauthorized"""
        with less_console_noise():
            # MOCK
            # mock that callback returns user_info; this is the expected behavior
            mock_client.callback.side_effect = self.user_info
            mock_auth.return_value = None
            # TEST
            with patch("djangooidc.views._requires_step_up_auth", return_value=False):
                response = self.client.get(reverse("openid_login_callback"))
            # ASSERTIONS
            self.assertEqual(response.status_code, 401)
            self.assertTemplateUsed(response, "401.html")
            self.assertIn("Unauthorized", response.content.decode("utf-8"))

    def test_logout_redirect_url(self, mock_client):
        """Test that logout redirects to the configured post_logout_redirect_uris."""
        with less_console_noise():
            # SETUP
            session = self.client.session
            session["state"] = "TEST"  # nosec B105
            session.save()
            # MOCK
            mock_client.callback.side_effect = self.user_info
            mock_client.registration_response = {"post_logout_redirect_uris": ["http://example.com/back"]}
            mock_client.provider_info = {"end_session_endpoint": "http://example.com/log_me_out"}
            mock_client.client_id = "TEST"
            # TEST
            with less_console_noise():
                response = self.client.get(reverse("logout"))
            # ASSERTIONS
            expected = (
                "http://example.com/log_me_out?client_id=TEST&state"
                "=TEST&post_logout_redirect_uri=http%3A%2F%2Fexample.com%2Fback"
            )
            actual = response.url
            self.assertEqual(response.status_code, 302)
            self.assertEqual(actual, expected)

    @patch("djangooidc.views.auth_logout")
    def test_logout_always_logs_out(self, mock_logout, _):
        """Without additional mocking, logout will always fail.
        Here we test that auth_logout is called regardless"""
        # TEST
        with less_console_noise():
            self.client.get(reverse("logout"))
        # ASSERTIONS
        self.assertTrue(mock_logout.called)

    def test_logout_callback_redirects(self, _):
        """Test that the logout_callback redirects properly"""
        with less_console_noise():
            # SETUP
            session = self.client.session
            session["next"] = reverse("logout")
            session.save()
            # TEST
            response = self.client.get(reverse("openid_logout_callback"))
            # ASSERTIONS
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse("logout"))
