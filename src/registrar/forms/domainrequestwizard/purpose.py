from django import forms
from django.core.validators import MaxLengthValidator
from registrar.forms.utility.wizard_form_helper import BaseDeletableRegistrarForm, BaseYesNoForm, RegistrarForm

class FEBPurposeOptionsForm(BaseDeletableRegistrarForm):

    field_name = "feb_purpose_choice"

    form_choices = (("new", "Used for a new website"), ("redirect", "Used as a redirect for an existing website"), ("other", "Not for a website"))

    feb_purpose_choice = forms.ChoiceField(
        required=True,
        choices=form_choices,
        widget=forms.RadioSelect,
        error_messages={
            "required": "This question is required.",
        },
        label = "Select one"
    )

class PurposeDetailsForm(BaseDeletableRegistrarForm):

    field_name="purpose"

    purpose = forms.CharField(
        label="Purpose",
        widget=forms.Textarea(
            attrs={
                "aria-label": "What is the purpose of your requested domain? Describe how you’ll use your .gov domain. \
                Will it be used for a website, email, or something else?"
            }
        ),
        validators=[
            MaxLengthValidator(
                2000,
                message="Response must be less than 2000 characters.",
            )
        ],
        error_messages={"required": "Describe how you’ll use the .gov domain you’re requesting."},
    )

class FEBTimeFrameYesNoForm(BaseDeletableRegistrarForm, BaseYesNoForm):
    """
    Form for determining whether the domain request comes with a target timeframe for launch.
    If the "no" option is selected, details must be provided via the separate details form.
    """

    field_name = "has_timeframe"

    @property
    def form_is_checked(self):
        """
        Determines the initial checked state of the form based on the domain_request's attributes.
        """
        return self.domain_request.has_timeframe


class FEBTimeFrameDetailsForm(BaseDeletableRegistrarForm):
    time_frame_details = forms.CharField(
        label="time_frame_details",
        widget=forms.Textarea(
            attrs={
                "aria-label": "Provide details on your target timeframe. \
                    Is there a special significance to this date (legal requirement, announcement, event, etc)?"
            }
        ),
        validators=[
            MaxLengthValidator(
                2000,
                message="Response must be less than 2000 characters.",
            )
        ],
        error_messages={"required": "Provide details on your target timeframe."},
    )

class FEBInteragencyInitiativeYesNoForm(BaseDeletableRegistrarForm, BaseYesNoForm):
    """
    Form for determining whether the domain request is part of an interagency initative.
    If the "no" option is selected, details must be provided via the separate details form.
    """

    field_name = "is_interagency_initiative"

    @property
    def form_is_checked(self):
        """
        Determines the initial checked state of the form based on the domain_request's attributes.
        """
        return self.domain_request.is_interagency_initiative


class FEBInteragencyInitiativeDetailsForm(BaseDeletableRegistrarForm):
    interagency_initiative_details = forms.CharField(
        label="interagency_initiative_details",
        widget=forms.Textarea(
            attrs={
                "aria-label": "Name the agencies that will be involved in this initiative."
            }
        ),
        validators=[
            MaxLengthValidator(
                2000,
                message="Response must be less than 2000 characters.",
            )
        ],
        error_messages={"required": "Name the agencies that will be involved in this initiative."},
    )