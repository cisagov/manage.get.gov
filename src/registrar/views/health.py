from django.http import HttpResponse


def health(request):
    return HttpResponse(
        '<html lang="en"><head><title>OK - Get.gov</title></head><body>OK</body>'
    )
