# coding: utf-8

import logging

from django.conf import settings
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import authenticate, login
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from urllib.parse import parse_qs, urlencode

from djangooidc.oidc import Client
from djangooidc import exceptions as o_e


logger = logging.getLogger(__name__)

try:
    # Initialize provider using pyOICD
    OP = getattr(settings, "OIDC_ACTIVE_PROVIDER")
    CLIENT = Client(OP)
    logger.debug("client initialized %s" % CLIENT)
except Exception as err:
    CLIENT = None  # type: ignore
    logger.warning(err)
    logger.warning("Unable to configure OpenID Connect provider. Users cannot log in.")


def error_page(request, error):
    """Display a sensible message and log the error."""
    logger.error(error)
    if isinstance(error, o_e.AuthenticationFailed):
        return render(
            request,
            "401.html",
            context={
                "friendly_message": error.friendly_message,
                "log_identifier": error.locator,
            },
            status=401,
        )
    if isinstance(error, o_e.InternalError):
        return render(
            request,
            "500.html",
            context={
                "friendly_message": error.friendly_message,
                "log_identifier": error.locator,
            },
            status=500,
        )
    if isinstance(error, Exception):
        return render(request, "500.html", status=500)


def openid(request):
    """Redirect the user to an authentication provider (OP)."""
    request.session["next"] = request.GET.get("next", "/")

    try:
        return CLIENT.create_authn_request(request.session)
    except Exception as err:
        return error_page(request, err)


def login_callback(request):
    """Analyze the token returned by the authentication provider (OP)."""
    try:
        query = parse_qs(request.GET.urlencode())
        userinfo = CLIENT.callback(query, request.session)
        user = authenticate(request=request, **userinfo)
        if user:
            login(request, user)
            logger.info("Successfully logged in user %s" % user)
            return redirect(request.session.get("next", "/"))
        else:
            raise o_e.BannedUser()
    except Exception as err:
        return error_page(request, err)


def logout(request, next_page=None):
    """Redirect the user to the authentication provider (OP) logout page."""
    try:
        username = request.user.username
        request_args = {
            "client_id": CLIENT.client_id,
            "state": request.session["state"],
        }
        if (
            "post_logout_redirect_uris" in CLIENT.registration_response.keys()
            and len(CLIENT.registration_response["post_logout_redirect_uris"]) > 0
        ):
            request_args.update(
                {
                    "post_logout_redirect_uri": CLIENT.registration_response[
                        "post_logout_redirect_uris"
                    ][0]
                }
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
        logger.info("Successfully logged out user %s" % username)
        next_page = getattr(settings, "LOGOUT_REDIRECT_URL", None)
        if next_page:
            request.session["next"] = next_page


def logout_callback(request):
    """Simple redirection view: after logout, redirect to `next`."""
    next = request.session.get("next", "/")
    return redirect(next)
