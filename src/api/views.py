"""Internal API views"""

from django.apps import apps
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse, JsonResponse
from django.utils.safestring import mark_safe

from registrar.templatetags.url_helpers import public_site_url
from registrar.utility.enums import ValidationReturnType
from registrar.utility.errors import GenericError, GenericErrorCodes

import requests

from login_required import login_not_required

from cachetools.func import ttl_cache

from registrar.utility.s3_bucket import S3ClientError, S3ClientHelper


RDAP_URL = "https://rdap.cloudflareregistry.com/rdap/domain/{domain}"


DOMAIN_API_MESSAGES = {
    "required": "Enter the .gov domain you want. Don’t include “www” or “.gov.”"
    " For example, if you want www.city.gov, you would enter “city”"
    " (without the quotes).",
    "extra_dots": "Enter the .gov domain you want without any periods.",
    # message below is considered safe; no user input can be inserted into the message
    # body; public_site_url() function reads from local app settings and therefore safe
    "unavailable": mark_safe(  # nosec
        "That domain isn’t available. "
        "<a class='usa-link' href='{}' target='_blank'>"
        "Read more about choosing your .gov domain</a>.".format(public_site_url("domains/choosing"))
    ),
    "invalid": "Enter a domain using only letters, numbers, or hyphens (though we don't recommend using hyphens).",
    "success": "That domain is available! We’ll try to give you the domain you want, \
               but it's not guaranteed. After you complete this form, we’ll \
               evaluate whether your request meets our requirements.",
    "error": GenericError.get_error_message(GenericErrorCodes.CANNOT_CONTACT_REGISTRY),
}


def check_domain_available(domain):
    """Return true if the given domain is available.

    The given domain is lowercased to match against the domains list. If the
    given domain doesn't end with .gov, ".gov" is added when looking for
    a match. If check fails, throws a RegistryError.
    """
    Domain = apps.get_model("registrar.Domain")

    if domain.endswith(".gov"):
        return Domain.available(domain)
    else:
        # domain search string doesn't end with .gov, add it on here
        return Domain.available(domain + ".gov")


@require_http_methods(["GET"])
@login_not_required
def available(request, domain=""):
    """Is a given domain available or not.

    Response is a JSON dictionary with the key "available" and value true or
    false.
    """
    Domain = apps.get_model("registrar.Domain")
    domain = request.GET.get("domain", "")

    _, json_response = Domain.validate_and_handle_errors(
        domain=domain,
        return_type=ValidationReturnType.JSON_RESPONSE,
    )
    return json_response


@require_http_methods(["GET"])
@login_not_required
# Since we cache domain RDAP data, cache time may need to be re-evaluated this if we encounter any memory issues
@ttl_cache(ttl=600)
def rdap(request, domain=""):
    """Returns JSON dictionary of a domain's RDAP data from Cloudflare API"""
    domain = request.GET.get("domain", "")

    # If inputted domain doesn't have a TLD, append .gov to it
    if "." not in domain:
        domain = f"{domain}.gov"

    rdap_data = requests.get(RDAP_URL.format(domain=domain), timeout=5).json()
    return JsonResponse(rdap_data)


@require_http_methods(["GET"])
@login_not_required
def get_current_full(request, file_name="current-full.csv"):
    """This will return the file content of current-full.csv which is the command
    output of generate_current_full_report.py. This command iterates through each Domain
    and returns a CSV representation."""
    return serve_file(file_name)


@require_http_methods(["GET"])
@login_not_required
def get_current_federal(request, file_name="current-federal.csv"):
    """This will return the file content of current-federal.csv which is the command
    output of generate_current_federal_report.py. This command iterates through each Domain
    and returns a CSV representation."""
    return serve_file(file_name)


def serve_file(file_name):
    """Downloads a file based on a given filepath. Returns a 500 if not found."""
    s3_client = S3ClientHelper()
    # Serve the CSV file. If not found, an exception will be thrown.
    # This will then be caught by flat, causing it to not read it - which is what we want.
    try:
        file = s3_client.get_file(file_name, decode_to_utf=True)
    except S3ClientError as err:
        # TODO - #1317: Notify operations when auto report generation fails
        raise err

    response = HttpResponse(file)
    return response
