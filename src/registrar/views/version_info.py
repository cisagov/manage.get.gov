from django.shortcuts import render
import os
from django.db import transaction
from registrar.decorators import grant_access, IS_STAFF


@grant_access(IS_STAFF)
@transaction.non_atomic_requests
def version_info(request):
    context = {
        "git_branch": os.getenv("GIT_BRANCH"),
        "git_commit_hash": os.getenv("GIT_COMMIT_SHA"),
        "git_tag": os.getenv("GIT_TAG"),
    }

    return render(request, "version-info.html", context)
