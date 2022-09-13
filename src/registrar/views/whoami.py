from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def whoami(request):
    """This is the first page someone goes to after logging in."""
    return render(request, "whoami.html")

