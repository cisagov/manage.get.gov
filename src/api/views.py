"""Internal API views"""


from django.views.decorators.http import require_http_methods
from django.http import JsonResponse

from django.contrib.auth.decorators import login_required

@require_http_methods(["GET"])
@login_required
def available(request, domain=""):

    """Is a given domain available or not.

    Response is a JSON dictionary with the key "available" and value true or
    false.
    """
    return JsonResponse({"available": False})

