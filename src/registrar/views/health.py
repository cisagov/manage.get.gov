from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def health(request):
    return HttpResponse(
        '<html lang="en"><head><title>OK - Get.gov</title></head><body>OK</body>'
    )


@login_required
def home(request):
    return render(
        request,
        "testapp/result.html",
        {
            "userinfo": request.session["userinfo"]
            if "userinfo" in request.session.keys()
            else None
        },
    )


def unprotected(request):
    return render(request, "testapp/unprotected.html")
