from django.http import HttpRequest
from waffle.decorators import flag_is_active
from waffle.models import get_waffle_flag_model


def flag_is_active_for_user(user, flag_name):
    """flag_is_active_for_user can be used when a waffle_flag may be
    activated for a user, but the context of where the flag needs to
    be tested does not have a request object available.
    When the request is available, flag_is_active should be used."""
    request = HttpRequest()
    request.user = user
    return flag_is_active(request, flag_name)


def flag_is_active_anywhere(flag_name):
    """Checks if the given flag name is active for anyone, anywhere.
    More specifically, it checks on flag.everyone or flag.users.exists().
    Does not check self.superuser, self.staff or self.group.

    This function effectively behaves like a switch:
    If said flag is enabled for someone, somewhere - return true.
    Otherwise - return false.
    """
    flag = get_waffle_flag_model().get(flag_name)
    if flag.everyone is None:
        return flag.users.exists()
    return flag.everyone
