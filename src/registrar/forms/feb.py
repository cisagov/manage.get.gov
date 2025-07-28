from django import forms
from django.core.validators import MaxLengthValidator
from registrar.forms.utility.wizard_form_helper import BaseDeletableRegistrarForm, BaseYesNoForm
from registrar.models.domain_request import DomainRequest


class ExecutiveNamingRequirementsYesNoForm(BaseYesNoForm, BaseDeletableRegistrarForm):
    """
    Form for verifying if the domain request meets the Federal Executive Branch domain naming requirements.
    If the "no" option is selected, details must be provided via the separate details form.
    """

    field_name = "feb_naming_requirements"

    required_error_message = "Select “Yes” if your submission meets each domain naming requirement. Select “No” if it doesn’t meet each requirement."  # noqa: E501

    @property
    def form_is_checked(self):
        """
        Determines the initial checked state of the form based on the domain_request's attributes.
        """
        return self.domain_request.feb_naming_requirements


class ExecutiveNamingRequirementsDetailsForm(BaseDeletableRegistrarForm):
    # Text area for additional details; rendered conditionally when "no" is selected.
    feb_naming_requirements_details = forms.CharField(
        widget=forms.Textarea(attrs={"maxlength": "2000"}),
        max_length=2000,
        required=True,
        error_messages={
            "required": ("Provide details on why your submission does not meet each domain naming requirement.")
        },  # noqa: E501
        validators=[
            MaxLengthValidator(
                2000,
                message="Response must be less than 2000 characters.",
            )
        ],
        label="",
        help_text="Maximum 2000 characters allowed.",
    )


class FEBPurposeOptionsForm(BaseDeletableRegistrarForm):

    field_name = "feb_purpose_choice"

    form_choices = DomainRequest.FEBPurposeChoices.choices

    feb_purpose_choice = forms.ChoiceField(
        required=True,
        choices=form_choices,
        widget=forms.RadioSelect,
        error_messages={
            "required": "Select the purpose of your requested domain.",
        },
        label="Select one",
    )


class FEBTimeFrameYesNoForm(BaseDeletableRegistrarForm, BaseYesNoForm):
    """
    Form for determining whether the domain request comes with a target timeframe for launch.
    If the "no" option is selected, details must be provided via the separate details form.
    """

    field_name = "has_timeframe"
    required_error_message = (
        "Select “Yes” if you have a target time frame for"
        " launching this domain. Select “No” if you don’t have a target time frame."
    )

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
                "aria-label": "Provide details on your target time frame. \
                    Is there a special significance to this date (legal requirement, announcement, event, etc)?"
            }
        ),
        validators=[
            MaxLengthValidator(
                2000,
                message="Response must be less than 2000 characters.",
            )
        ],
        error_messages={"required": "Provide details on your target time frame."},
    )


class FEBInteragencyInitiativeYesNoForm(BaseDeletableRegistrarForm, BaseYesNoForm):
    """
    Form for determining whether the domain request is part of an interagency initative.
    If the "no" option is selected, details must be provided via the separate details form.
    """

    field_name = "is_interagency_initiative"
    required_error_message = (
        "Select “Yes” if the domain will be used for an "
        "interagency initiative. Select “No” if it won’t be used for an interagency initiative."
    )

    @property
    def form_is_checked(self):
        """
        Determines the initial checked state of the form based on the domain_request's attributes.
        """
        return self.domain_request.is_interagency_initiative


class FEBInteragencyInitiativeDetailsForm(BaseDeletableRegistrarForm):
    interagency_initiative_details = forms.CharField(
        label="interagency_initiative_details",
        widget=forms.Textarea(attrs={"aria-label": "Provide details on the nature of the interagency initiative."}),
        validators=[
            MaxLengthValidator(
                2000,
                message="Response must be less than 2000 characters.",
            )
        ],
        error_messages={"required": "Provide details on the nature of the interagency initiative."},
    )


class FEBAnythingElseYesNoForm(BaseYesNoForm, BaseDeletableRegistrarForm):
    """Yes/no toggle for the anything else question on additional details"""

    form_is_checked = property(lambda self: self.domain_request.has_anything_else_text)  # type: ignore
    field_name = "has_anything_else_text"
