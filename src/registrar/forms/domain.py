"""Forms for domain management."""

from django import forms

from registrar.models import User


class DomainAddUserForm(forms.Form):

    """Form for adding a user to a domain."""

    email = forms.EmailField(label="Email")

    def clean_email(self):
        requested_email = self.cleaned_data["email"]
        try:
            User.objects.get(email=requested_email)
        except User.DoesNotExist:
            # TODO: send an invitation email to a non-existent user
            raise forms.ValidationError("That user does not exist in this system.")
        return requested_email
