from django import forms
from django.core.validators import MaxLengthValidator
from registrar.forms.utility.wizard_form_helper import BaseDeletableRegistrarForm, BaseYesNoForm
from registrar.models.contact import Contact


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
        # if not obj.eop_contact:
        #     return {}
        # return {
        #     "first_name": obj.feb_eop_contact.first_name,
        #     "last_name": obj.feb_eop_contact.last_name,
        #     "email": obj.feb_eop_contact.email,
        # }
        return {}

    def to_database(self, obj):
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
