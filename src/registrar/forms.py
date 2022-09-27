from django import forms

from .models import UserProfile


class EditProfileForm(forms.ModelForm):

    """Custom form class for editing a UserProfile.

    We can add whatever fields we want to this form and customize how they
    are displayed. The form is rendered into a template `profile.html` by a
    view called `edit_profile` in `profile.py`.
    """

    display_name = forms.CharField(
        widget=forms.TextInput(attrs={"class": "usa-input"}), label="Display Name"
    )

    class Meta:
        model = UserProfile
        fields = ["display_name"]
