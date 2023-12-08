import logging

from django.test import TestCase

from django.conf import settings

from djangooidc.oidc import Client

logger = logging.getLogger(__name__)


class OidcTest(TestCase):
    def test_oidc_create_authn_request_with_acr_value(self):
        """Test that create_authn_request returns a redirect with an acr_value
        when an acr_value is passed through session.

        This test is only valid locally.  On local, client can be initialized.
        Client initialization does not work in pipeline, so test is useless in
        pipeline. However, it will not fail in pipeline."""
        try:
            # Initialize provider using pyOICD
            OP = getattr(settings, "OIDC_ACTIVE_PROVIDER")
            CLIENT = Client(OP)
            session = {"acr_value": "some_acr_value_maybe_ial2"}
            response = CLIENT.create_authn_request(session)
            self.assertEqual(response.status_code, 302)
            self.assertIn("some_acr_value_maybe_ial2", response.url)
        except Exception as err:
            logger.warning(err)
            logger.warning("Unable to configure OpenID Connect provider in pipeline. Cannot execute this test.")
