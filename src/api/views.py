"""Internal API views"""


from django.views.decorators.http import require_http_methods
from django.http import JsonResponse

from django.contrib.auth.decorators import login_required

import requests

from cachetools.func import ttl_cache

DOMAIN_FILE_URL = "https://raw.githubusercontent.com/cisagov/dotgov-data/main/current-full.csv"


# this file doesn't change that often, nor is it that big, so cache the result
# in memory for ten minutes
@ttl_cache(ttl=600)
def _domains():
    """Return a list of the current .gov domains.

    Fetch a file from DOMAIN_FILE_URL, parse the CSV for the domain,
    lowercase everything and return the list.
    """
    file_contents = requests.get(DOMAIN_FILE_URL).text
    domains = set()
    # skip the first line
    for line in file_contents.splitlines()[1:]:
        # get the domain before the first comma
        domain = line.split(",", 1)[0]
        # lowercase everything
        domains.add(domain.lower())
    return domains


def in_domains(domain):
    """Return true if the given domain is in the domains list.

    The given domain is lowercased to match against the domains list.
    """
    return domain.lower() in _domains()


@require_http_methods(["GET"])
@login_required
def available(request, domain=""):

    """Is a given domain available or not.

    Response is a JSON dictionary with the key "available" and value true or
    false.
    """
    # a domain is available if it is NOT in the list of current domains
    return JsonResponse({"available": not in_domains(domain)})

