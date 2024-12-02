from django.shortcuts import render
from django.http import HttpResponse


def index(request):
    """This page is available to anyone without logging in."""

    # TEST SESSION
    # request.session['key'] = 'sup'
    # value = request.session.get('key', 'not set')
    # request.session.flush()
    # return HttpResponse(f"Session key is {value}")


    context = {}

    if request and request.user and request.user.is_authenticated:
        # This controls the creation of a new domain request in the wizard
        context["user_domain_count"] = request.user.get_user_domain_ids(request).count()

    return render(request, "home.html", context)
