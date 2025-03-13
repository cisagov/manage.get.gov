from django import forms
from django.core.validators import MaxLengthValidator
from registrar.forms.utility.wizard_form_helper import BaseDeletableRegistrarForm, BaseYesNoForm
from registrar.models.contact import Contact


class ExecutiveNamingRequirementsYesNoForm(BaseYesNoForm, BaseDeletableRegistrarForm):
    """
    Form for verifying if the domain request meets the Federal Executive Branch domain naming requirements.
    If the "no" option is selected, details must be provided via the separate details form.
    """

    field_name = "feb_naming_requirements"

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
        error_messages={"required": ("This field is required.")},
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

    form_choices = (
        ("new", "Used for a new website"),
        ("redirect", "Used as a redirect for an existing website"),
        ("other", "Not for a website"),
    )

    feb_purpose_choice = forms.ChoiceField(
        required=True,
        choices=form_choices,
        widget=forms.RadioSelect,
        error_messages={
            "required": "This question is required.",
        },
        label="Select one",
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
        widget=forms.Textarea(attrs={"aria-label": "Name the agencies that will be involved in this initiative."}),
        validators=[
            MaxLengthValidator(
                2000,
                message="Response must be less than 2000 characters.",
            )
        ],
        error_messages={"required": "Name the agencies that will be involved in this initiative."},
    )


class WorkingWithEOPYesNoForm(BaseDeletableRegistrarForm, BaseYesNoForm):
    """
    Form for determining if the Federal Executive Branch (FEB) agency is working with the
    Executive Office of the President (EOP) on the domain request.
    """

    field_name = "working_with_eop"

    @property
    def form_is_checked(self):
        """
        Determines the initial checked state of the form based on the domain_request's attributes.
        """
        return self.domain_request.working_with_eop


class EOPContactForm(BaseDeletableRegistrarForm):
    """
    Form for contact information of the representative of the
    Executive Office of the President (EOP) that the Federal
    Executive Branch (FEB) agency is working with.
    """

    field_name = "eop_contact"

    first_name = forms.CharField(
        label="First name / given name",
        error_messages={"required": "Enter the first name / given name of this contact."},
        required=True,
    )
    last_name = forms.CharField(
        label="Last name / family name",
        error_messages={"required": "Enter the last name / family name of this contact."},
        required=True,
    )
    email = forms.EmailField(
        label="Email",
        max_length=None,
        error_messages={
            "required": ("Enter an email address in the required format, like name@example.com."),
            "invalid": ("Enter an email address in the required format, like name@example.com."),
        },
        validators=[
            MaxLengthValidator(
                320,
                message="Response must be less than 320 characters.",
            )
        ],
        required=True,
        help_text="Enter an email address in the required format, like name@example.com.",
    )

    @classmethod
    def from_database(cls, obj):
        if not obj.eop_contact:
            return {}
        return {
            "first_name": obj.eop_contact.first_name,
            "last_name": obj.eop_contact.last_name,
            "email": obj.eop_contact.email,
        }

    def to_database(self, obj):
        # This function overrides the behavior of the BaseDeletableRegistrarForm.
        # in order to preserve deletable functionality, we need to call the
        # superclass's to_database method if the form is marked for deletion.
        if self.form_data_marked_for_deletion:
            super().to_database(obj)
            return
        if not self.is_valid():
            return
        obj.eop_contact = Contact.objects.create(
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            email=self.cleaned_data["email"],
        )
        obj.save()


class FEBAnythingElseYesNoForm(BaseYesNoForm, BaseDeletableRegistrarForm):
    """Yes/no toggle for the anything else question on additional details"""

    form_is_checked = property(lambda self: self.domain_request.has_anything_else_text)  # type: ignore
    field_name = "has_anything_else_text"
