from django.http import HttpRequest
from waffle.decorators import flag_is_active

def flag_is_active_for_user(user, flag_name):
    """flag_is_active_for_user can be used when a waffle_flag may be
    activated for a user, but the context of where the flag needs to
    be tested does not have a request object available.
    When the request is available, flag_is_active should be used."""
    request = HttpRequest()
    request.user = user
    return flag_is_active(request, flag_name)