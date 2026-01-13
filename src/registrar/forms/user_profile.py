from django import forms

from registrar.models.user import User

from django.core.validators import MaxLengthValidator
from phonenumber_field.widgets import RegionalPhoneNumberWidget
from registrar.models.utility.domain_helper import DomainHelper


class UserProfileForm(forms.ModelForm):
    """Form for updating user profile."""
    """Making a random change"

    redirect = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = User
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
        """Override the inerited __init__ method to update the fields."""

        super().__init__(*args, **kwargs)
        # take off maxlength attribute for the phone number field
        # which interferes with out input_with_errors template tag
        self.fields["phone"].widget.attrs.pop("maxlength", None)

        # Define a custom validator for the email field with a custom error message
        email_max_length_validator = MaxLengthValidator(320, message="Response must be less than 320 characters.")
        self.fields["email"].validators.append(email_max_length_validator)

        for field_name in self.required:
            self.fields[field_name].required = True

        # Set custom form label
        self.fields["first_name"].label = "First name / given name"
        self.fields["middle_name"].label = "Middle name (optional)"
        self.fields["last_name"].label = "Last name / family name"
        self.fields["title"].label = "Title or role in your organization"
        self.fields["email"].label = "Organization email"

        # Set custom error messages
        self.fields["first_name"].error_messages = {"required": "Enter your first name / given name."}
        self.fields["last_name"].error_messages = {"required": "Enter your last name / family name."}
        self.fields["title"].error_messages = {
            "required": "Enter your title or role in your organization (e.g., Chief Information Officer)"
        }
        self.fields["email"].error_messages = {
            "required": "Enter an email address in the required format, like name@example.com."
        }
        self.fields["email"].widget.attrs["hide_character_count"] = "True"
        self.fields["phone"].error_messages["required"] = "Enter your phone number."

        if self.instance and self.instance.phone:
            self.fields["phone"].initial = self.instance.phone.as_national

        DomainHelper.disable_field(self.fields["email"], disable_required=True)


class FinishSetupProfileForm(UserProfileForm):
    """Form for updating user profile."""

    full_name = forms.CharField(required=False, label="Full name")

    def clean(self):
        cleaned_data = super().clean()
        # Remove the full name property
        if "full_name" in cleaned_data:
            # Delete the full name element as its purely decorative.
            # We include it as a normal Charfield for all the advantages
            # and utility that it brings, but we're playing pretend.
            del cleaned_data["full_name"]
        return cleaned_data

    def __init__(self, *args, **kwargs):
        """Override the inerited __init__ method to update the fields."""

        super().__init__(*args, **kwargs)

        # Set custom form label for email
        self.fields["email"].label = "Organization email"
        self.fields["title"].label = "Title or role in your organization"

        # Define the "full_name" value
        full_name = None
        if self.instance.first_name and self.instance.last_name:
            full_name = self.instance.get_formatted_name()
        self.fields["full_name"].initial = full_name
