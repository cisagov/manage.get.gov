from login_required import login_not_required
from django.shortcuts import render
import os


@login_not_required
def version_info(request):
    context = {
        "git_branch": os.getenv("GIT_BRANCH"),
        "git_commit_hash": os.getenv("GIT_COMMIT_SHA"),
        "git_tag": os.getenv("GIT_TAG"),
    }

    return render(request, "version-info.html", context)
