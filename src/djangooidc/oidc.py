# coding: utf-8
from __future__ import unicode_literals

import logging
import json

from django.conf import settings
from django.http import HttpResponseRedirect
from Cryptodome.PublicKey.RSA import importKey
from jwkest.jwk import RSAKey  # type: ignore
from oic import oic, rndstr
from oic.oauth2 import ErrorResponse
from oic.oic import AuthorizationRequest, AuthorizationResponse, RegistrationResponse
from oic.oic.message import AccessTokenResponse
from oic.utils.authn.client import CLIENT_AUTHN_METHOD
from oic.utils import keyio

from . import exceptions as o_e

__author__ = "roland"

logger = logging.getLogger(__name__)


class Client(oic.Client):
    def __init__(self, op):
        """Step 1: Configure the OpenID Connect client."""
        logger.debug("Initializing the OpenID Connect client...")
        try:
            provider = settings.OIDC_PROVIDERS[op]
            verify_ssl = getattr(settings, "OIDC_VERIFY_SSL", True)
        except Exception as err:
            logger.error(err)
            logger.error("Configuration missing for OpenID Connect client")
            raise o_e.InternalError()

        try:
            # prepare private key for authentication method of private_key_jwt
            key_bundle = keyio.KeyBundle()
            rsa_key = importKey(provider["client_registration"]["sp_private_key"])
            key = RSAKey(key=rsa_key, use="sig")
            key_bundle.append(key)
            keyjar = keyio.KeyJar(verify_ssl=verify_ssl)
            keyjar.add_kb("", key_bundle)
        except Exception as err:
            logger.error(err)
            logger.error(
                "Key jar preparation failed for %s",
                provider["srv_discovery_url"],
            )
            raise o_e.InternalError()

        try:
            # create the oic client instance
            super().__init__(
                client_id=None,
                client_authn_method=CLIENT_AUTHN_METHOD,
                keyjar=keyjar,
                verify_ssl=verify_ssl,
                config=None,
            )
            # must be set after client is initialized
            self.behaviour = provider["behaviour"]
        except Exception as err:
            logger.error(err)
            logger.error(
                "Client creation failed for %s",
                provider["srv_discovery_url"],
            )
            raise o_e.InternalError()

        try:
            # discover and store the provider (OP) urls, etc
            self.provider_config(provider["srv_discovery_url"])
            self.store_registration_info(
                RegistrationResponse(**provider["client_registration"])
            )
        except Exception as err:
            logger.error(err)
            logger.error(
                "Provider info discovery failed for %s",
                provider["srv_discovery_url"],
            )
            raise o_e.InternalError()

    def create_authn_request(
        self,
        session,
        extra_args=None,
    ):
        """Step 2: Construct a login URL at OP's domain and send the user to it."""
        logger.debug("Creating the OpenID Connect authn request...")
        state = rndstr(size=32)
        try:
            session["state"] = state
            session["nonce"] = rndstr(size=32)
            scopes = list(self.behaviour.get("scope", []))
            scopes.append("openid")
            request_args = {
                "response_type": self.behaviour.get("response_type"),
                "scope": " ".join(set(scopes)),
                "state": session["state"],
                "nonce": session["nonce"],
                "redirect_uri": self.registration_response["redirect_uris"][0],
                "acr_values": self.behaviour.get("acr_value"),
            }

            if extra_args is not None:
                request_args.update(extra_args)
        except Exception as err:
            logger.error(err)
            logger.error("Failed to assemble request arguments for %s" % state)
            raise o_e.InternalError(locator=state)

        logger.debug("request args: %s" % request_args)

        try:
            # prepare the request for sending
            cis = self.construct_AuthorizationRequest(request_args=request_args)
            logger.debug("request: %s" % cis)

            # obtain the url and headers from the prepared request
            url, body, headers, cis = self.uri_and_body(
                AuthorizationRequest,
                cis,
                method="GET",
                request_args=request_args,
            )
            logger.debug("body: %s" % body)
            logger.debug("URL: %s" % url)
            logger.debug("headers: %s" % headers)
        except Exception as err:
            logger.error(err)
            logger.error("Failed to prepare request for %s" % state)
            raise o_e.InternalError(locator=state)

        try:
            # create the redirect object
            response = HttpResponseRedirect(str(url))
            # add headers to the object, if any
            if headers:
                for key, value in headers.items():
                    response[key] = value
        except Exception as err:
            logger.error(err)
            logger.error("Failed to create redirect object for %s" % state)
            raise o_e.InternalError(locator=state)

        return response

    def callback(self, unparsed_response, session):
        """Step 3: Receive OP's response, request an access token, and user info."""
        logger.debug("Processing the OpenID Connect callback response...")
        state = session.get("state", "")
        try:
            # parse the response from OP
            authn_response = self.parse_response(
                AuthorizationResponse,
                unparsed_response,
                sformat="dict",
                keyjar=self.keyjar,
            )
        except Exception as err:
            logger.error(err)
            logger.error("Unable to parse response for %s" % state)
            raise o_e.AuthenticationFailed(locator=state)

        # ErrorResponse is not raised, it is passed back...
        if isinstance(authn_response, ErrorResponse):
            error = authn_response.get("error", "")
            if error == "login_required":
                logger.warning(
                    "User was not logged in (%s), trying again for %s" % (error, state)
                )
                return self.create_authn_request(session)
            else:
                logger.error("Unable to process response %s for %s" % (error, state))
                raise o_e.AuthenticationFailed(locator=state)

        logger.debug("authn_response %s" % authn_response)

        if not authn_response.get("state", None):
            logger.error("State value not received from OP for %s" % state)
            raise o_e.AuthenticationFailed(locator=state)

        if authn_response["state"] != session.get("state", None):
            # this most likely means the user's Django session vanished
            logger.error("Received state not the same as expected for %s" % state)
            raise o_e.AuthenticationFailed(locator=state)

        if self.behaviour.get("response_type") == "code":
            # need an access token to get user info (and to log the user out later)
            self._request_token(
                authn_response["state"], authn_response["code"], session
            )

        user_info = self._get_user_info(state, session)

        return user_info

    def _get_user_info(self, state, session):
        """Get information from OP about the user."""
        scopes = list(self.behaviour.get("user_info_request", []))
        scopes.append("openid")
        try:
            # get info about the user from OP
            info_response = self.do_user_info_request(
                state=session["state"],
                method="GET",
                scope=" ".join(set(scopes)),
            )
        except Exception as err:
            logger.error(err)
            logger.error("Unable to request user info for %s" % state)
            raise o_e.AuthenticationFailed(locator=state)

        # ErrorResponse is not raised, it is passed back...
        if isinstance(info_response, ErrorResponse):
            logger.error(
                "Unable to get user info (%s) for %s"
                % (info_response.get("error", ""), state)
            )
            raise o_e.AuthenticationFailed(locator=state)

        logger.debug("user info: %s" % info_response)
        return info_response.to_dict()

    def _request_token(self, state, code, session):
        """Request a token from OP to allow us to then request user info."""
        try:
            token_response = self.do_access_token_request(
                scope="openid",
                state=state,
                request_args={
                    "code": code,
                    "redirect_uri": self.registration_response["redirect_uris"][0],
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                authn_method=self.registration_response["token_endpoint_auth_method"],
            )
        except Exception as err:
            logger.error(err)
            logger.error("Unable to obtain access token for %s" % state)
            raise o_e.AuthenticationFailed(locator=state)

        # ErrorResponse is not raised, it is passed back...
        if isinstance(token_response, ErrorResponse):
            logger.error(
                "Unable to get token (%s) for %s"
                % (token_response.get("error", ""), state)
            )
            raise o_e.AuthenticationFailed(locator=state)

        logger.debug("token response %s" % token_response)

        try:
            # get the token and other bits of info
            id_token = token_response["id_token"]._dict

            if id_token["nonce"] != session["nonce"]:
                logger.error("Received nonce not the same as expected for %s" % state)
                raise o_e.AuthenticationFailed(locator=state)

            session["id_token"] = id_token
            session["id_token_raw"] = getattr(self, "id_token_raw", None)
            session["access_token"] = token_response["access_token"]
            session["refresh_token"] = token_response.get("refresh_token", "")
            session["expires_in"] = token_response.get("expires_in", "")
            self.id_token[state] = getattr(self, "id_token_raw", None)
        except Exception as err:
            logger.error(err)
            logger.error("Unable to parse access token response for %s" % state)
            raise o_e.AuthenticationFailed(locator=state)

    def store_response(self, resp, info):
        """Make raw ID token available for internal use."""
        if isinstance(resp, AccessTokenResponse):
            info = json.loads(info)
            self.id_token_raw = info["id_token"]

        super(Client, self).store_response(resp, info)

    def __repr__(self):
        return "Client {} {} {}".format(
            self.client_id,
            self.client_prefs,
            self.behaviour,
        )
