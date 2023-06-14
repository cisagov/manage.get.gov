"""Forms for domain management."""

from django import forms
from django.core.validators import RegexValidator
from django.forms import formset_factory

from phonenumber_field.widgets import RegionalPhoneNumberWidget

from ..models import Contact, DomainInformation


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
    required = ["first_name", "last_name", "title", "email", "phone"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # take off maxlength attribute for the phone number field
        # which interferes with out input_with_errors template tag
        self.fields["phone"].widget.attrs.pop("maxlength", None)

        for field_name in self.required:
            self.fields[field_name].required = True


class DomainSecurityEmailForm(forms.Form):

    """Form for adding or editing a security email to a domain."""

    security_email = forms.EmailField(label="Security email")


class DomainOrgNameAddressForm(forms.ModelForm):

    """Form for updating the organization name and mailing address."""

    zipcode = forms.CharField(
        label="Zip code",
        validators=[
            RegexValidator(
                "^[0-9]{5}(?:-[0-9]{4})?$|^$",
                message="Enter a zip code in the form of 12345 or 12345-6789.",
            )
        ],
    )

    class Meta:
        model = DomainInformation
        fields = [
            "federal_agency",
            "organization_name",
            "address_line1",
            "address_line2",
            "city",
            "state_territory",
            "zipcode",
            "urbanization",
        ]
        error_messages = {
            "federal_agency": {
                "required": "Select the federal agency for your organization."
            },
            "organization_name": {"required": "Enter the name of your organization."},
            "address_line1": {
                "required": "Enter the street address of your organization."
            },
            "city": {"required": "Enter the city where your organization is located."},
            "state_territory": {
                "required": "Select the state, territory, or military post where your"
                "organization  is located."
            },
        }
        widgets = {
            # We need to set the required attributed for federal_agency and
            # state/territory because for these fields we are creating an individual
            # instance of the Select. For the other fields we use the for loop to set
            # the class's required attribute to true.
            "federal_agency": forms.Select(
                attrs={"required": True}, choices=DomainInformation.AGENCY_CHOICES
            ),
            "organization_name": forms.TextInput,
            "address_line1": forms.TextInput,
            "address_line2": forms.TextInput,
            "city": forms.TextInput,
            "state_territory": forms.Select(
                attrs={
                    "required": True,
                },
                choices=DomainInformation.StateTerritoryChoices.choices,
            ),
            "urbanization": forms.TextInput,
        }

    # the database fields have blank=True so ModelForm doesn't create
    # required fields by default. Use this list in __init__ to mark each
    # of these fields as required
    required = ["organization_name", "address_line1", "city", "zipcode"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.required:
            self.fields[field_name].required = True
        self.fields["state_territory"].widget.attrs.pop("maxlength", None)
        self.fields["zipcode"].widget.attrs.pop("maxlength", None)
