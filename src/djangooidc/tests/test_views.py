from unittest.mock import patch

from django.http import HttpResponse
from django.test import Client, TestCase
from django.urls import reverse

from .common import less_console_noise


@patch("djangooidc.views.CLIENT", autospec=True)
class ViewsTest(TestCase):
    def setUp(self):
        self.client = Client()

    def say_hi(*args):
        return HttpResponse("Hi")

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
        # setup
        callback_url = reverse("openid_login_callback")
        # mock
        mock_client.create_authn_request.side_effect = self.say_hi
        # test
        response = self.client.get(reverse("login"), {"next": callback_url})
        # assert
        session = mock_client.create_authn_request.call_args[0][0]
        self.assertEqual(session["next"], callback_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hi")

    def test_openid_raises(self, mock_client):
        # mock
        mock_client.create_authn_request.side_effect = Exception("Test")
        # test
        with less_console_noise():
            response = self.client.get(reverse("login"))
        # assert
        self.assertEqual(response.status_code, 500)
        self.assertTemplateUsed(response, "500.html")
        self.assertIn("Server Error", response.content.decode("utf-8"))

    def test_login_callback_reads_next(self, mock_client):
        # setup
        session = self.client.session
        session["next"] = reverse("logout")
        session.save()
        # mock
        mock_client.callback.side_effect = self.user_info
        # test
        with less_console_noise():
            response = self.client.get(reverse("openid_login_callback"))
        # assert
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("logout"))

    @patch("djangooidc.views.authenticate")
    def test_login_callback_raises(self, mock_auth, mock_client):
        # mock
        mock_client.callback.side_effect = self.user_info
        mock_auth.return_value = None
        # test
        with less_console_noise():
            response = self.client.get(reverse("openid_login_callback"))
        # assert
        self.assertEqual(response.status_code, 401)
        self.assertTemplateUsed(response, "401.html")
        self.assertIn("Unauthorized", response.content.decode("utf-8"))

    def test_logout_redirect_url(self, mock_client):
        # setup
        session = self.client.session
        session["id_token_raw"] = "TEST"  # nosec B105
        session["state"] = "TEST"  # nosec B105
        session.save()
        # mock
        mock_client.callback.side_effect = self.user_info
        mock_client.registration_response = {
            "post_logout_redirect_uris": ["http://example.com/back"]
        }
        mock_client.provider_info = {
            "end_session_endpoint": "http://example.com/log_me_out"
        }
        # test
        with less_console_noise():
            response = self.client.get(reverse("logout"))
        # assert
        expected = (
            "http://example.com/log_me_out?id_token_hint=TEST&state"
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
        # setup
        session = self.client.session
        session["next"] = reverse("logout")
        session.save()
        # test
        response = self.client.get(reverse("openid_logout_callback"))
        # assert
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("logout"))
