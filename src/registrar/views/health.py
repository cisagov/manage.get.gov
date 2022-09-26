from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def health(request):
    return HttpResponse(
        '<html lang="en"><head><title>OK - Get.gov</title></head><body>OK</body>'
    )
