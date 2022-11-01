"""Internal API views"""


import re

from django.core.exceptions import BadRequest
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse

from django.contrib.auth.decorators import login_required

import requests

from cachetools.func import ttl_cache

DOMAIN_FILE_URL = (
    "https://raw.githubusercontent.com/cisagov/dotgov-data/main/current-full.csv"
)
# a domain name is alphanumeric or hyphen, up to 63 characters, doesn't
# begin or end with a hyphen, followed by a TLD of 2-6 alphabetic characters
DOMAIN_REGEX = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)\.[A-Za-z]{2,6}")


def string_could_be_domain(domain):
    """Return True if the string could be a domain name, otherwise False.

    TODO: when we have a Domain class, this could be a classmethod there.
    """
    if DOMAIN_REGEX.match(domain):
        return True
    return False


# this file doesn't change that often, nor is it that big, so cache the result
# in memory for ten minutes
@ttl_cache(ttl=600)
def _domains():
    """Return a list of the current .gov domains.

    Fetch a file from DOMAIN_FILE_URL, parse the CSV for the domain,
    lowercase everything and return the list.
    """
    # 5 second timeout
    file_contents = requests.get(DOMAIN_FILE_URL, timeout=5).text
    domains = set()
    # skip the first line
    for line in file_contents.splitlines()[1:]:
        # get the domain before the first comma
        domain = line.split(",", 1)[0]
        # sanity-check the string we got from the file here
        if string_could_be_domain(domain):
            # lowercase everything when we put it in domains
            domains.add(domain.lower())
    return domains


def in_domains(domain):
    """Return true if the given domain is in the domains list.

    The given domain is lowercased to match against the domains list. If the
    given domain doesn't end with .gov, ".gov" is added when looking for
    a match.
    """
    domain = domain.lower()
    if domain.endswith(".gov"):
        return domain.lower() in _domains()
    else:
        # domain search string doesn't end with .gov, add it on here
        return (domain + ".gov") in _domains()


@require_http_methods(["GET"])
@login_required
def available(request, domain=""):

    """Is a given domain available or not.

    Response is a JSON dictionary with the key "available" and value true or
    false.
    """
    # validate that the given domain could be a domain name and fail early if
    # not.
    if not (string_could_be_domain(domain) or string_could_be_domain(domain + ".gov")):
        raise BadRequest("Invalid request.")
    # a domain is available if it is NOT in the list of current domains
    return JsonResponse({"available": not in_domains(domain)})
