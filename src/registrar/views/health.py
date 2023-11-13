from django.http import HttpResponse

from login_required import login_not_required


# the health check endpoint needs to be globally available so that the
# PaaS orchestrator can make sure the app has come up properly
@login_not_required
def health(request):
    return HttpResponse('<html lang="en"><head><title>OK - Get.gov</title></head><body>OK</body>')
