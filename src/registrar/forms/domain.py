"""Forms for domain management."""

from django import forms


class DomainAddUserForm(forms.Form):

    """Form for adding a user to a domain."""

    email = forms.EmailField(label="Email")


class DomainNameserverForm(forms.Form):

    """Form for changing nameservers."""

    server = forms.CharField(label="Name server")
