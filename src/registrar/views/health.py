from django.http import HttpResponse
from django.conf import settings
from login_required import login_not_required
from django.shortcuts import render
import os

# the health check endpoint needs to be globally available so that the
# PaaS orchestrator can make sure the app has come up properly
@login_not_required
def health(request):

    context = {
        "git_branch": os.getenv('GIT_BRANCH', 'Not Found'),
        "git_commit_hash":os.getenv('GIT_COMMIT', 'Not Found'),
        "git_tag": os.getenv('GIT_TAG', ''),
    }

    return render(request, "health.html", context)
