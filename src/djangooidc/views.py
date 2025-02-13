# coding: utf-8

import logging

from django.conf import settings
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import authenticate, login
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from urllib.parse import parse_qs, urlencode

from djangooidc.oidc import Client
from djangooidc import exceptions as o_e
from registrar.models import User
from registrar.views.utility.error_views import custom_500_error_view, custom_401_error_view

logger = logging.getLogger(__name__)

CLIENT = None


def _initialize_client():
    """Initialize the OIDC client. Exceptions are allowed to raise
    and will need to be caught."""
    global CLIENT
    # Initialize provider using pyOICD
    OP = getattr(settings, "OIDC_ACTIVE_PROVIDER")
    CLIENT = Client(OP)
    logger.debug("Client initialized: %s" % CLIENT)


def _client_is_none():
    """Return if the CLIENT is currently None."""
    global CLIENT
    return CLIENT is None


# Initialize CLIENT
try:
    _initialize_client()
except Exception as err:
    # In the event of an exception, log the error and allow the app load to continue
    # without the OIDC Client. Subsequent login attempts will attempt to initialize
    # again if Client is None
    logger.error(err)
    logger.error("Unable to configure OpenID Connect provider. Users cannot log in.")


def error_page(request, error):
    """Display a sensible message and log the error."""
    logger.error(error)
    if isinstance(error, o_e.AuthenticationFailed):
        context = {
            "friendly_message": error.friendly_message,
            "log_identifier": error.locator,
        }
        return custom_401_error_view(request, context)
    if isinstance(error, o_e.InternalError):
        context = {
            "friendly_message": error.friendly_message,
            "log_identifier": error.locator,
        }
        return custom_500_error_view(request, context)
    if isinstance(error, Exception):
        return custom_500_error_view(request)


def openid(request):
    """Redirect the user to an authentication provider (OP)."""
    global CLIENT
    try:
        # If the CLIENT is none, attempt to reinitialize before handling the request
        if _client_is_none():
            logger.debug("OIDC client is None, attempting to initialize")
            _initialize_client()
        request.session["acr_value"] = CLIENT.get_default_acr_value()
        request.session["next"] = request.GET.get("next", "/")
        # Create the authentication request
        return CLIENT.create_authn_request(request.session)
    except Exception as err:
        return error_page(request, err)


def login_callback(request):
    """Analyze the token returned by the authentication provider (OP)."""
    global CLIENT
    try:
        # If the CLIENT is none, attempt to reinitialize before handling the request
        if _client_is_none():
            logger.debug("OIDC client is None, attempting to initialize")
            _initialize_client()
        query = parse_qs(request.GET.urlencode())
        userinfo = CLIENT.callback(query, request.session)
        # test for need for identity verification and if it is satisfied
        # if not satisfied, redirect user to login with stepped up acr_value
        if _requires_step_up_auth(userinfo):
            # add acr_value to request.session
            request.session["acr_value"] = CLIENT.get_step_up_acr_value()
            return CLIENT.create_authn_request(request.session)
        user = authenticate(request=request, **userinfo)
        if user:

            # Fixture users kind of exist in a superposition of verification types,
            # because while the system "verified" them, if they login,
            # we don't know how the user themselves was verified through login.gov until
            # they actually try logging in. This edge-case only matters in non-production environments.
            fixture_user = User.VerificationTypeChoices.FIXTURE_USER
            is_fixture_user = user.verification_type and user.verification_type == fixture_user

            # Set the verification type if it doesn't already exist or if its a fixture user
            if not user.verification_type or is_fixture_user:
                user.set_user_verification_type()
                user.save()

            login(request, user)
            logger.info("Successfully logged in user %s" % user)

            # Clear the flag if the exception is not caught
            request.session.pop("redirect_attempted", None)
            return redirect(request.session.get("next", "/"))
        else:
            raise o_e.BannedUser()
    except o_e.StateMismatch as nsd_err:
        # Check if the redirect has already been attempted
        if not request.session.get("redirect_attempted", False):
            # Set the flag to indicate that the redirect has been attempted
            request.session["redirect_attempted"] = True

            # In the event of a state mismatch between OP and session, redirect the user to the
            # beginning of login process without raising an error to the user. Attempt once.
            logger.warning(f"No State Defined: {nsd_err}")
            return redirect(request.session.get("next", "/"))
        else:
            # Clear the flag if the exception is not caught
            request.session.pop("redirect_attempted", None)
            return error_page(request, nsd_err)
    except Exception as err:
        return error_page(request, err)


def _requires_step_up_auth(userinfo):
    """if User.needs_identity_verification and step_up_acr_value not in
    ial returned from callback, return True"""
    step_up_acr_value = CLIENT.get_step_up_acr_value()
    acr_value = userinfo.get("ial", "")
    uuid = userinfo.get("sub", "")
    email = userinfo.get("email", "")
    if acr_value != step_up_acr_value:
        # The acr of this attempt is not at the highest level
        # so check if the user needs the higher level
        return User.needs_identity_verification(email, uuid)
    else:
        # This attempt already came back at the highest level
        # so does not require step up
        return False


def logout(request, next_page=None):
    """Redirect the user to the authentication provider (OP) logout page."""
    try:
        user = request.user
        request_args = {
            "client_id": CLIENT.client_id,
        }
        # if state is not in request session, still redirect to the identity
        # provider's logout url, but don't include the state in the url; this
        # will successfully log out of the identity provider
        if "state" in request.session:
            request_args["state"] = request.session["state"]
        if (
            "post_logout_redirect_uris" in CLIENT.registration_response.keys()
            and len(CLIENT.registration_response["post_logout_redirect_uris"]) > 0
        ):
            request_args.update(
                {"post_logout_redirect_uri": CLIENT.registration_response["post_logout_redirect_uris"][0]}
            )
        url = CLIENT.provider_info["end_session_endpoint"]
        url += "?" + urlencode(request_args)
        return HttpResponseRedirect(url)
    except Exception as err:
        return error_page(request, err)
    finally:
        # Always remove Django session stuff - even if not logged out from OP.
        # Don't wait for the callback as it may never come.
        auth_logout(request)
        logger.info("Successfully logged out user %s" % user)
        next_page = getattr(settings, "LOGOUT_REDIRECT_URL", None)
        if next_page:
            request.session["next"] = next_page


def logout_callback(request):
    """Simple redirection view: after logout, redirect to `next`."""
    next = request.session.get("next", "/")
    return redirect(next)
