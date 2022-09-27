from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from ..forms import EditProfileForm


@login_required
def edit_profile(request):

    """View for a profile editing page."""

    if request.method == "POST":
        # post to this view when changes are made
        profile_form = EditProfileForm(request.POST, instance=request.user.userprofile)
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, "Your profile is updated successfully")
            return redirect(to="edit-profile")
    else:
        profile_form = EditProfileForm(instance=request.user.userprofile)
    return render(request, "profile.html", {"profile_form": profile_form})
