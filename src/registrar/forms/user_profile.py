from django import forms

from registrar.models.contact import Contact

from django.core.validators import MaxLengthValidator
from phonenumber_field.widgets import RegionalPhoneNumberWidget

class UserProfileForm(forms.ModelForm):
    """Form for updating user profile."""

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

    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     # take off maxlength attribute for the phone number field
    #     # which interferes with out input_with_errors template tag
    #     self.fields["phone"].widget.attrs.pop("maxlength", None)

    #     # Define a custom validator for the email field with a custom error message
    #     email_max_length_validator = MaxLengthValidator(320, message="Response must be less than 320 characters.")
    #     self.fields["email"].validators.append(email_max_length_validator)

    #     for field_name in self.required:
    #         self.fields[field_name].required = True

    #     # Set custom form label
    #     self.fields["middle_name"].label = "Middle name (optional)"

    #     # Set custom error messages
    #     self.fields["first_name"].error_messages = {"required": "Enter your first name / given name."}
    #     self.fields["last_name"].error_messages = {"required": "Enter your last name / family name."}
    #     self.fields["title"].error_messages = {
    #         "required": "Enter your title or role in your organization (e.g., Chief Information Officer)"
    #     }
    #     self.fields["email"].error_messages = {
    #         "required": "Enter your email address in the required format, like name@example.com."
    #     }
    #     self.fields["phone"].error_messages["required"] = "Enter your phone number."
    #     self.domainInfo = None 