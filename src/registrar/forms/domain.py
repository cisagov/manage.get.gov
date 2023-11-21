"""Forms for domain management."""

from django import forms
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.forms import formset_factory

from phonenumber_field.widgets import RegionalPhoneNumberWidget
from registrar.utility.errors import (
    NameserverError,
    NameserverErrorCodes as nsErrorCodes,
    DsDataError,
    DsDataErrorCodes,
    SecurityEmailError,
    SecurityEmailErrorCodes,
)

from ..models import Contact, DomainInformation, Domain
from .common import (
    ALGORITHM_CHOICES,
    DIGEST_TYPE_CHOICES,
)

import re


class DomainAddUserForm(forms.Form):
    """Form for adding a user to a domain."""

    email = forms.EmailField(label="Email")


class DomainNameserverForm(forms.Form):
    """Form for changing nameservers."""

    domain = forms.CharField(widget=forms.HiddenInput, required=False)

    server = forms.CharField(label="Name server", strip=True)

    ip = forms.CharField(
        label="IP address (IPv4 or IPv6)",
        strip=True,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super(DomainNameserverForm, self).__init__(*args, **kwargs)

        # add custom error messages
        self.fields["server"].error_messages.update(
            {
                "required": "A minimum of 2 name servers are required.",
            }
        )

    def clean(self):
        # clean is called from clean_forms, which is called from is_valid
        # after clean_fields.  it is used to determine form level errors.
        # is_valid is typically called from view during a post
        cleaned_data = super().clean()
        self.clean_empty_strings(cleaned_data)
        server = cleaned_data.get("server", "")
        # remove ANY spaces in the server field
        server = server.replace(" ", "")
        # lowercase the server
        server = server.lower()
        cleaned_data["server"] = server
        ip = cleaned_data.get("ip", None)
        # remove ANY spaces in the ip field
        ip = ip.replace(" ", "")
        domain = cleaned_data.get("domain", "")

        ip_list = self.extract_ip_list(ip)

        # validate if the form has a server or an ip
        if (ip and ip_list) or server:
            self.validate_nameserver_ip_combo(domain, server, ip_list)

        return cleaned_data

    def clean_empty_strings(self, cleaned_data):
        ip = cleaned_data.get("ip", "")
        if ip and len(ip.strip()) == 0:
            cleaned_data["ip"] = None

    def extract_ip_list(self, ip):
        return [ip.strip() for ip in ip.split(",")] if ip else []

    def validate_nameserver_ip_combo(self, domain, server, ip_list):
        try:
            Domain.checkHostIPCombo(domain, server, ip_list)
        except NameserverError as e:
            if e.code == nsErrorCodes.GLUE_RECORD_NOT_ALLOWED:
                self.add_error(
                    "server",
                    NameserverError(
                        code=nsErrorCodes.GLUE_RECORD_NOT_ALLOWED,
                        nameserver=domain,
                        ip=ip_list,
                    ),
                )
            elif e.code == nsErrorCodes.MISSING_IP:
                self.add_error(
                    "ip",
                    NameserverError(code=nsErrorCodes.MISSING_IP, nameserver=domain, ip=ip_list),
                )
            elif e.code == nsErrorCodes.MISSING_HOST:
                self.add_error(
                    "server",
                    NameserverError(code=nsErrorCodes.MISSING_HOST, nameserver=domain, ip=ip_list),
                )
            elif e.code == nsErrorCodes.INVALID_HOST:
                self.add_error(
                    "server",
                    NameserverError(code=nsErrorCodes.INVALID_HOST, nameserver=server, ip=ip_list),
                )
            else:
                self.add_error("ip", str(e))


NameserverFormset = formset_factory(
    DomainNameserverForm,
    extra=1,
    max_num=13,
    validate_max=True,
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

    security_email = forms.EmailField(
        label="Security email",
        required=False,
        error_messages={
            "invalid": str(SecurityEmailError(code=SecurityEmailErrorCodes.BAD_DATA)),
        },
    )


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
            "federal_agency": {"required": "Select the federal agency for your organization."},
            "organization_name": {"required": "Enter the name of your organization."},
            "address_line1": {"required": "Enter the street address of your organization."},
            "city": {"required": "Enter the city where your organization is located."},
            "state_territory": {
                "required": "Select the state, territory, or military post where your organization is located."
            },
        }
        widgets = {
            # We need to set the required attributed for federal_agency and
            # state/territory because for these fields we are creating an individual
            # instance of the Select. For the other fields we use the for loop to set
            # the class's required attribute to true.
            "federal_agency": forms.Select(attrs={"required": True}, choices=DomainInformation.AGENCY_CHOICES),
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


class DomainDnssecForm(forms.Form):
    """Form for enabling and disabling dnssec"""


class DomainDsdataForm(forms.Form):
    """Form for adding or editing DNSSEC DS Data to a domain."""

    def validate_hexadecimal(value):
        """
        Tests that string matches all hexadecimal values.

        Raise validation error to display error in form
        if invalid characters entered
        """
        if not re.match(r"^[0-9a-fA-F]+$", value):
            raise forms.ValidationError(str(DsDataError(code=DsDataErrorCodes.INVALID_DIGEST_CHARS)))

    key_tag = forms.IntegerField(
        required=True,
        label="Key tag",
        validators=[
            MinValueValidator(0, message=str(DsDataError(code=DsDataErrorCodes.INVALID_KEYTAG_SIZE))),
            MaxValueValidator(65535, message=str(DsDataError(code=DsDataErrorCodes.INVALID_KEYTAG_SIZE))),
        ],
        error_messages={"required": ("Key tag is required.")},
    )

    algorithm = forms.TypedChoiceField(
        required=True,
        label="Algorithm",
        coerce=int,  # need to coerce into int so dsData objects can be compared
        choices=[(None, "--Select--")] + ALGORITHM_CHOICES,  # type: ignore
        error_messages={"required": ("Algorithm is required.")},
    )

    digest_type = forms.TypedChoiceField(
        required=True,
        label="Digest type",
        coerce=int,  # need to coerce into int so dsData objects can be compared
        choices=[(None, "--Select--")] + DIGEST_TYPE_CHOICES,  # type: ignore
        error_messages={"required": ("Digest type is required.")},
    )

    digest = forms.CharField(
        required=True,
        label="Digest",
        validators=[validate_hexadecimal],
        max_length=64,
        error_messages={
            "required": "Digest is required.",
            "max_length": str(DsDataError(code=DsDataErrorCodes.INVALID_DIGEST_LENGTH)),
        },
    )

    def clean(self):
        # clean is called from clean_forms, which is called from is_valid
        # after clean_fields.  it is used to determine form level errors.
        # is_valid is typically called from view during a post
        cleaned_data = super().clean()
        digest_type = cleaned_data.get("digest_type", 0)
        digest = cleaned_data.get("digest", "")
        # validate length of digest depending on digest_type
        if digest_type == 1 and len(digest) != 40:
            self.add_error(
                "digest",
                DsDataError(code=DsDataErrorCodes.INVALID_DIGEST_SHA1),
            )
        elif digest_type == 2 and len(digest) != 64:
            self.add_error(
                "digest",
                DsDataError(code=DsDataErrorCodes.INVALID_DIGEST_SHA256),
            )
        return cleaned_data


DomainDsdataFormset = formset_factory(
    DomainDsdataForm,
    extra=0,
    can_delete=True,
)
