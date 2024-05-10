from django import forms
from phonenumber_field.formfields import PhoneNumberField  # type: ignore
from django.core.validators import MaxLengthValidator


class ContactForm(forms.Form):
    """Form for adding or editing a contact"""

    def to_database(self, obj):
        """
        Adds this form's cleaned data to `obj` and saves `obj`.

        Does nothing if form is not valid.
        """
        if not self.is_valid():
            return
        for name, value in self.cleaned_data.items():
            setattr(obj, name, value)
        obj.save()

    @classmethod
    def from_database(cls, obj):
        """Returns a dict of form field values gotten from `obj`."""
        if obj is None:
            return {}
        return {name: getattr(obj, name) for name in cls.declared_fields.keys()}  # type: ignore

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

