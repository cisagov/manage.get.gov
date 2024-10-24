"""Forms for portfolio."""

import logging
from django import forms
from django.core.validators import RegexValidator
from django.core.validators import MaxLengthValidator

from registrar.models import (
    PortfolioInvitation,
    UserPortfolioPermission,
    DomainInformation,
    Portfolio,
    SeniorOfficial,
    User,
)
from registrar.models.utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices

logger = logging.getLogger(__name__)


class PortfolioOrgAddressForm(forms.ModelForm):
    """Form for updating the portfolio org mailing address."""

    zipcode = forms.CharField(
        label="Zip code",
        validators=[
            RegexValidator(
                "^[0-9]{5}(?:-[0-9]{4})?$|^$",
                message="Enter a 5-digit or 9-digit zip code, like 12345 or 12345-6789.",
            )
        ],
        error_messages={
            "required": "Enter a 5-digit or 9-digit zip code, like 12345 or 12345-6789.",
        },
    )

    class Meta:
        model = Portfolio
        fields = [
            "address_line1",
            "address_line2",
            "city",
            "state_territory",
            "zipcode",
            # "urbanization",
        ]
        error_messages = {
            "address_line1": {"required": "Enter the street address of your organization."},
            "city": {"required": "Enter the city where your organization is located."},
            "state_territory": {
                "required": "Select the state, territory, or military post where your organization is located."
            },
            "zipcode": {"required": "Enter a 5-digit or 9-digit zip code, like 12345 or 12345-6789."},
        }
        widgets = {
            # We need to set the required attributed for State/territory
            # because for this fields we are creating an individual
            # instance of the Select. For the other fields we use the for loop to set
            # the class's required attribute to true.
            "address_line1": forms.TextInput,
            "address_line2": forms.TextInput,
            "city": forms.TextInput,
            "state_territory": forms.Select(
                attrs={
                    "required": True,
                },
                choices=DomainInformation.StateTerritoryChoices.choices,
            ),
            # "urbanization": forms.TextInput,
        }

    # the database fields have blank=True so ModelForm doesn't create
    # required fields by default. Use this list in __init__ to mark each
    # of these fields as required
    required = ["address_line1", "city", "state_territory", "zipcode"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.required:
            self.fields[field_name].required = True
        self.fields["state_territory"].widget.attrs.pop("maxlength", None)
        self.fields["zipcode"].widget.attrs.pop("maxlength", None)


class PortfolioSeniorOfficialForm(forms.ModelForm):
    """
    Form for updating the portfolio senior official.
    This form is readonly for now.
    """

    JOIN = "senior_official"
    full_name = forms.CharField(label="Full name", required=False)

    class Meta:
        model = SeniorOfficial
        fields = [
            "title",
            "email",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.id:
            self.fields["full_name"].initial = self.instance.get_formatted_name()

    def clean(self):
        """Clean override to remove unused fields"""
        cleaned_data = super().clean()
        cleaned_data.pop("full_name", None)
        return cleaned_data


class PortfolioMemberForm(forms.ModelForm):
    """
    Form for updating a portfolio member.
    """

    roles = forms.MultipleChoiceField(
        choices=UserPortfolioRoleChoices.choices,
        widget=forms.SelectMultiple(attrs={"class": "usa-select"}),
        required=False,
        label="Roles",
    )

    additional_permissions = forms.MultipleChoiceField(
        choices=UserPortfolioPermissionChoices.choices,
        widget=forms.SelectMultiple(attrs={"class": "usa-select"}),
        required=False,
        label="Additional Permissions",
    )

    class Meta:
        model = UserPortfolioPermission
        fields = [
            "roles",
            "additional_permissions",
        ]


class PortfolioInvitedMemberForm(forms.ModelForm):
    """
    Form for updating a portfolio invited member.
    """

    roles = forms.MultipleChoiceField(
        choices=UserPortfolioRoleChoices.choices,
        widget=forms.SelectMultiple(attrs={"class": "usa-select"}),
        required=False,
        label="Roles",
    )

    additional_permissions = forms.MultipleChoiceField(
        choices=UserPortfolioPermissionChoices.choices,
        widget=forms.SelectMultiple(attrs={"class": "usa-select"}),
        required=False,
        label="Additional Permissions",
    )

    class Meta:
        model = PortfolioInvitation
        fields = [
            "roles",
            "additional_permissions",
        ]


class NewMemberForm(forms.ModelForm):
    member_access_level = forms.ChoiceField(
        label="Select permission",
        choices=[("admin", "Admin Access"), ("basic", "Basic Access")],
        widget=forms.RadioSelect(attrs={'class': 'usa-radio__input  usa-radio__input--tile'}),
        required=True,
        error_messages={
            "required": "Member access level is required",
        },
    )
    admin_org_domain_request_permissions = forms.ChoiceField(
        label="Select permission",
        choices=[("view_only", "View all requests"), ("view_and_create", "View all requests plus create requests")],
        widget=forms.RadioSelect,
        required=True,
        error_messages={
            "required": "Domain request permission is required",
        },
    )
    admin_org_members_permissions = forms.ChoiceField(
        label="Select permission",
        choices=[("view_only", "View all members"), ("view_and_create", "View all members plus manage members")],
        widget=forms.RadioSelect,
        required=True,
        error_messages={
            "required": "Member permission is required",
        },
    )
    basic_org_domain_request_permissions = forms.ChoiceField(
        label="Select permission",
        choices=[
            ("view_only", "View all requests"),
            ("view_and_create", "View all requests plus create requests"),
            ("no_access", "No access"),
        ],
        widget=forms.RadioSelect,
        required=True,
        error_messages={
            "required": "Member permission is required",
        },
    )

    email = forms.EmailField(
        label="Enter the email of the member you'd like to invite",
        max_length=None,
        error_messages={
            "invalid": ("Enter an email address in the required format, like name@example.com."),
            "required": ("Enter an email address in the required format, like name@example.com."),
        },
        validators=[
            MaxLengthValidator(
                320,
                message="Response must be less than 320 characters.",
            )
        ],
        required=True,
    )

    class Meta:
        model = User
        fields = ["email"]

    def clean(self):
        cleaned_data = super().clean()

        # Lowercase the value of the 'email' field
        email_value = cleaned_data.get("email")
        if email_value:
            cleaned_data["email"] = email_value.lower()

        # Check for an existing user (if there isn't any, send an invite)
        # if email_value:
        #     try:
        #         existingUser = User.objects.get(email=email_value)
        #     except User.DoesNotExist:
        #         raise forms.ValidationError("User with this email does not exist.")

        # Get the grade and sport from POST data
        permission_level = cleaned_data.get("member_access_level")
        # permission_level = self.data.get('new_member-permission_level')
        if not permission_level:
            for field in self.fields:
                if field in self.errors and field != "email" and field != "member_access_level":
                    del self.errors[field]
            return cleaned_data

        # Validate the sport based on the selected grade
        if permission_level == "True":
            #remove the error messages pertaining to basic permission inputs
            del self.errors["basic_org_domain_request_permissions"]
        else:
            #remove the error messages pertaining to admin permission inputs
            del self.errors["admin_org_domain_request_permissions"]
            del self.errors["admin_org_members_permissions"]
        return cleaned_data
