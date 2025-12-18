from django.http import HttpResponse
from django.conf import settings
from login_required import login_not_required
from django.shortcuts import render


# the health check endpoint needs to be globally available so that the
# PaaS orchestrator can make sure the app has come up properly
@login_not_required
def health(request):

    context = {
        'git_branch': settings.GIT_BRANCH,
        'git_commit_hash':  settings.GIT_COMMIT_HASH,
        'git_tag': settings.GIT_TAG,
        'is_tag': settings.IS_TAG
    }

    return render(request, "health.html", context)
