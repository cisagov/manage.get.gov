from unittest.mock import MagicMock, patch

from django.http import HttpResponse
from django.test import Client, TestCase, RequestFactory
from django.urls import reverse

from djangooidc.exceptions import NoStateDefined
from ..views import login_callback

from .common import less_console_noise


@patch("djangooidc.views.CLIENT", autospec=True)
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
        with less_console_noise():
            # setup
            callback_url = reverse("openid_login_callback")
            # mock
            mock_client.create_authn_request.side_effect = self.say_hi
            mock_client.get_default_acr_value.side_effect = self.create_acr
            # test
            response = self.client.get(reverse("login"), {"next": callback_url})
            # assert
            session = mock_client.create_authn_request.call_args[0][0]
            self.assertEqual(session["next"], callback_url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Hi")

    def test_openid_raises(self, mock_client):
        with less_console_noise():
            # mock
            mock_client.create_authn_request.side_effect = Exception("Test")
            # test
            response = self.client.get(reverse("login"))
            # assert
            self.assertEqual(response.status_code, 500)
            self.assertTemplateUsed(response, "500.html")
            self.assertIn("Server error", response.content.decode("utf-8"))

    def test_callback_with_no_session_state(self, mock_client):
        """If the local session is None (ie the server restarted while user was logged out),
        we do not throw an exception. Rather, we attempt to login again."""
        with less_console_noise():
            # mock
            mock_client.get_default_acr_value.side_effect = self.create_acr
            mock_client.callback.side_effect = NoStateDefined()
            # test
            response = self.client.get(reverse("openid_login_callback"))
            # assert
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, "/")

    def test_login_callback_reads_next(self, mock_client):
        with less_console_noise():
            # setup
            session = self.client.session
            session["next"] = reverse("logout")
            session.save()
            # mock
            mock_client.callback.side_effect = self.user_info
            # test
            with patch("djangooidc.views._requires_step_up_auth", return_value=False), less_console_noise():
                response = self.client.get(reverse("openid_login_callback"))
            # assert
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse("logout"))

    def test_login_callback_no_step_up_auth(self, mock_client):
        """Walk through login_callback when _requires_step_up_auth returns False
        and assert that we have a redirect to /"""
        with less_console_noise():
            # setup
            session = self.client.session
            session.save()
            # mock
            mock_client.callback.side_effect = self.user_info
            # test
            with patch("djangooidc.views._requires_step_up_auth", return_value=False), less_console_noise():
                response = self.client.get(reverse("openid_login_callback"))
            # assert
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, "/")

    def test_requires_step_up_auth(self, mock_client):
        """Invoke login_callback passing it a request when _requires_step_up_auth returns True
        and assert that session is updated and create_authn_request (mock) is called."""
        with less_console_noise():
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
                login_callback(request)
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
            # Create a mock request
            request = self.factory.get("/some-url")
            request.session = {"acr_value": ""}
            # Ensure that the CLIENT instance used in login_callback is the mock
            # patch _requires_step_up_auth to return False
            with patch("djangooidc.views._requires_step_up_auth", return_value=False), patch(
                "djangooidc.views.CLIENT.create_authn_request", return_value=MagicMock()
            ) as mock_create_authn_request:
                login_callback(request)
            # create_authn_request only gets called when _requires_step_up_auth is True
            # and it changes this acr_value in request.session
            # Assert that acr_value is NOT updated by testing that it is still an empty string
            self.assertEqual(request.session["acr_value"], "")
            # Assert create_authn_request was not called
            mock_create_authn_request.assert_not_called()

    @patch("djangooidc.views.authenticate")
    def test_login_callback_raises(self, mock_auth, mock_client):
        with less_console_noise():
            # mock
            mock_client.callback.side_effect = self.user_info
            mock_auth.return_value = None
            # test
            with patch("djangooidc.views._requires_step_up_auth", return_value=False), less_console_noise():
                response = self.client.get(reverse("openid_login_callback"))
            # assert
            self.assertEqual(response.status_code, 401)
            self.assertTemplateUsed(response, "401.html")
            self.assertIn("Unauthorized", response.content.decode("utf-8"))

    def test_logout_redirect_url(self, mock_client):
        with less_console_noise():
            # setup
            session = self.client.session
            session["state"] = "TEST"  # nosec B105
            session.save()
            # mock
            mock_client.callback.side_effect = self.user_info
            mock_client.registration_response = {"post_logout_redirect_uris": ["http://example.com/back"]}
            mock_client.provider_info = {"end_session_endpoint": "http://example.com/log_me_out"}
            mock_client.client_id = "TEST"
            # test
            with less_console_noise():
                response = self.client.get(reverse("logout"))
            # assert
            expected = (
                "http://example.com/log_me_out?client_id=TEST&state"
                "=TEST&post_logout_redirect_uri=http%3A%2F%2Fexample.com%2Fback"
            )
            actual = response.url
            self.assertEqual(response.status_code, 302)
            self.assertEqual(actual, expected)

    @patch("djangooidc.views.auth_logout")
    def test_logout_always_logs_out(self, mock_logout, _):
        # Without additional mocking, logout will always fail.
        # Here we test that auth_logout is called regardless
        with less_console_noise():
            self.client.get(reverse("logout"))
        self.assertTrue(mock_logout.called)

    def test_logout_callback_redirects(self, _):
        with less_console_noise():
            # setup
            session = self.client.session
            session["next"] = reverse("logout")
            session.save()
            # test
            response = self.client.get(reverse("openid_logout_callback"))
            # assert
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse("logout"))
