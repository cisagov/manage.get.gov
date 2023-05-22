"""Forms for domain management."""

from django import forms
from django.forms import formset_factory

from phonenumber_field.widgets import RegionalPhoneNumberWidget

from ..models import Contact


class DomainAddUserForm(forms.Form):

    """Form for adding a user to a domain."""

    email = forms.EmailField(label="Email")


class DomainNameserverForm(forms.Form):

    """Form for changing nameservers."""

    server = forms.CharField(label="Name server")


NameserverFormset = formset_factory(
    DomainNameserverForm,
    extra=1,
)


class DomainSecurityEmailForm(forms.Form):

    """Form for adding or editing a security email to a domain."""

    security_email = forms.EmailField(label="Security email")
    
    
class ContactForm(forms.ModelForm):

    """Form for updating contacts."""

    class Meta:
        model = Contact
        fields = ["first_name", "middle_name", "last_name", "title", "email", "phone"]
        widgets = {
            "first_name": forms.TextInput,
            "middle_name": forms.TextInput,
            "last_name": forms.TextInput,
            "title": forms.TextInput,
            "email": forms.EmailInput,
            "phone": RegionalPhoneNumberWidget,
        }

    # the database fields have blank=True so ModelForm doesn't create
    # required fields by default. Use this list in __init__ to mark each
    # of these fields as required
    required = [
        "first_name",
        "last_name",
        "title",
        "email",
        "phone"
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # take off maxlength attribute for the phone number field
        # which interferes with out input_with_errors template tag
        self.fields['phone'].widget.attrs.pop('maxlength', None)

        for field_name in self.required:
            self.fields[field_name].required = True
    
    
