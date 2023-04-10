"""Forms for domain management."""

from django import forms


class DomainAddUserForm(forms.Form):

    """Form for adding a user to a domain."""

    email = forms.EmailField(label="Email")
