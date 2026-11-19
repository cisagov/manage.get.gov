from django import forms
from django.core.validators import MaxLengthValidator

from registrar.validations import EMAIL_MAX, TEXT_EXTENDED


class MaxLengthFirstEmailField(forms.EmailField):
    """Email field that returns max-length errors before format errors."""

    def __init__(self, *args, email_max_length=EMAIL_MAX, email_max_length_message=None, **kwargs):
        self.email_max_length_validator = MaxLengthValidator(
            email_max_length,
            message=email_max_length_message or f"Email must be no more than {email_max_length} characters.",
        )
        super().__init__(*args, **kwargs)

    def run_validators(self, value):
        self.email_max_length_validator(value)
        super().run_validators(value)


class MaxLengthFirstURLField(forms.URLField):
    """URL field that returns max-length errors before format errors."""

    def __init__(self, *args, url_max_length=TEXT_EXTENDED, url_max_length_message=None, **kwargs):
        self.url_max_length_validator = MaxLengthValidator(
            url_max_length,
            message=url_max_length_message or f"Website must be no more than {url_max_length} characters.",
        )
        super().__init__(*args, **kwargs)

    def clean(self, value):
        if value:
            self.url_max_length_validator(value)
        return super().clean(value)
