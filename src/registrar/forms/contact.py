from django import forms
from phonenumber_field.formfields import PhoneNumberField  # type: ignore


class ContactForm(forms.Form):
    """Form for adding or editing a contact"""

    def clean(self):
        cleaned_data = super().clean()
        # Remove the full name property
        if "full_name" in cleaned_data:
            full_name: str = cleaned_data["full_name"]
            if full_name:
                name_fields = full_name.split(" ")

                
                cleaned_data["first_name"] = name_fields[0]
                if len(name_fields) == 2:
                    cleaned_data["last_name"] = " ".join(name_fields[1:])
                elif len(name_fields) > 2:
                    cleaned_data["middle_name"] = name_fields[1]
                    cleaned_data["last_name"] = " ".join(name_fields[2:])
                else:
                    cleaned_data["middle_name"] = None
                    cleaned_data["last_name"] = None

                # Delete the full name element as we don't need it anymore
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
    )
    phone = PhoneNumberField(
        label="Phone",
        error_messages={"invalid": "Enter a valid 10-digit phone number.", "required": "Enter your phone number."},
    )

