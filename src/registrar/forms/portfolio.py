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


class PortfolioNewMemberForm(forms.ModelForm):
    member_access_level = forms.ChoiceField(
        label="Select permission",
        choices=[("organization_admin", "Admin Access"), ("organization_member", "Basic Access")],
        widget=forms.RadioSelect(attrs={"class": "usa-radio__input  usa-radio__input--tile"}),
        required=True,
        error_messages={
            "required": "Member access level is required",
        },
    )
    admin_org_domain_request_permissions = forms.ChoiceField(
        label="Select permission",
        choices=[("view_all_requests", "View all requests"), ("edit_requests", "View all requests plus create requests")],
        widget=forms.RadioSelect,
        required=True,
        error_messages={
            "required": "Admin domain request permission is required",
        },
    )
    admin_org_members_permissions = forms.ChoiceField(
        label="Select permission",
        choices=[("view_members", "View all members"), ("edit_members", "View all members plus manage members")],
        widget=forms.RadioSelect,
        required=True,
        error_messages={
            "required": "Admin member permission is required",
        },
    )
    basic_org_domain_request_permissions = forms.ChoiceField(
        label="Select permission",
        choices=[
            ("view_all_requests", "View all requests"),
            ("edit_requests", "View all requests plus create requests"),
            ("", "No access"),
        ],
        widget=forms.RadioSelect,
        required=True,
        error_messages={
            "required": "Basic member permission is required",
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
        model = PortfolioInvitation
        fields = ["portfolio", "email", "roles", "additional_permissions"]

    def is_valid(self):
        logger.info("is valid()")
        return super().is_valid()
    
    def full_clean(self):
        logger.info("full_clean()")
        super().full_clean()

    def _clean_fields(self):
        logger.info("clean fields")
        logger.info(self.fields)
        super()._clean_fields()

    def _post_clean(self):
        logger.info("post clean")
        logger.info(self.cleaned_data)
        super()._post_clean()
        logger.info(self.instance)

    def clean(self):
        logger.info(self.cleaned_data)
        logger.info(self.initial)
        # Lowercase the value of the 'email' field
        email_value = self.cleaned_data.get("email")
        if email_value:
            self.cleaned_data["email"] = email_value.lower()

        # Get the selected member access level
        member_access_level = self.cleaned_data.get("member_access_level")

        # If no member access level is selected, remove errors for hidden inputs
        if not member_access_level:
            self._remove_hidden_field_errors(exclude_fields=["email", "member_access_level"])
            return self.cleaned_data

        # Define field names for validation cleanup
        field_error_map = {
            "organization_admin": ["basic_org_domain_request_permissions"],  # Fields irrelevant to "admin"
            "organization_member": ["admin_org_domain_request_permissions", "admin_org_members_permissions"],  # Fields irrelevant to "basic"
        }

        # Remove errors for irrelevant fields based on the selected access level
        irrelevant_fields = field_error_map.get(member_access_level, [])
        for field in irrelevant_fields:
            if field in self.errors:
                del self.errors[field]

        # Map roles and additional permissions to cleaned_data
        self.cleaned_data["roles"] = [member_access_level]
        additional_permissions = [
            self.cleaned_data.get("admin_org_domain_request_permissions"),
            self.cleaned_data.get("basic_org_domain_request_permissions"),
            self.cleaned_data.get("admin_org_members_permissions"),
        ]
        # Filter out None values
        self.cleaned_data["additional_permissions"] = [perm for perm in additional_permissions if perm]

        return super().clean()

    def _remove_hidden_field_errors(self, exclude_fields=None):
        """
        Helper method to remove errors for fields that are not relevant
        (e.g., hidden inputs), except for explicitly excluded fields.
        """
        exclude_fields = exclude_fields or []
        hidden_fields = [field for field in self.fields if field not in exclude_fields]
        for field in hidden_fields:
            if field in self.errors:
                del self.errors[field]

