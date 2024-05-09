from django import forms
from phonenumber_field.modelfields import PhoneNumberField  # type: ignore
from django.core.validators import MaxLengthValidator


class ContactForm(forms.Form):
    """Form for adding or editing a contact"""

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
        label="Email",
        max_length=None,
        error_messages={"invalid": ("Enter your email address in the required format, like name@example.com.")},
        validators=[
            MaxLengthValidator(
                320,
                message="Response must be less than 320 characters.",
            )
        ],
    )
    phone = PhoneNumberField(
        label="Phone",
        error_messages={"invalid": "Enter a valid 10-digit phone number.", "required": "Enter your phone number."},
    )

