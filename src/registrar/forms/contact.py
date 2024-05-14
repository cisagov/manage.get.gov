from django import forms
from phonenumber_field.formfields import PhoneNumberField  # type: ignore


class ContactForm(forms.Form):
    """Form for adding or editing a contact"""

    def clean(self):
        cleaned_data = super().clean()
        # Remove the full name property
        if "full_name" in cleaned_data:
            # Delete the full name element as its purely decorative.
            # We include it as a normal Charfield for all the advantages
            # and utility that it brings, but we're playing pretend.
            del cleaned_data["full_name"]
        return cleaned_data

    full_name = forms.CharField(
        label="Full name",
        error_messages={"required": "Enter your full name"},
    )
    first_name = forms.CharField(
        label="First name / given name",
        error_messages={"required": "Enter your first name / given name."},
    )
    middle_name = forms.CharField(
        required=False,
        label="Middle name (optional)",
    )
    last_name = forms.CharField(
        label="Last name / family name",
        error_messages={"required": "Enter your last name / family name."},
    )
    title = forms.CharField(
        label="Title or role in your organization",
        error_messages={
            "required": ("Enter your title or role in your organization (e.g., Chief Information Officer).")
        },
    )
    email = forms.EmailField(
        label="Organization email",
        required=False,
        max_length=None,
    )
    phone = PhoneNumberField(
        label="Phone",
        error_messages={"invalid": "Enter a valid 10-digit phone number.", "required": "Enter your phone number."},
    )

