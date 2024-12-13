"""Forms for portfolio."""

import logging
from django import forms
from django.core.validators import RegexValidator
from django.core.validators import MaxLengthValidator
from django.utils.safestring import mark_safe
from registrar.models import (
    PortfolioInvitation,
    UserPortfolioPermission,
    DomainInformation,
    Portfolio,
    SeniorOfficial,
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


class BasePortfolioMemberForm(forms.Form):
    required_star = '<abbr class="usa-hint usa-hint--required" title="required">*</abbr>'
    role = forms.ChoiceField(
        choices=[
            (UserPortfolioRoleChoices.ORGANIZATION_ADMIN.value, "Admin access"),
            (UserPortfolioRoleChoices.ORGANIZATION_MEMBER.value, "Basic access"),
        ],
        widget=forms.RadioSelect,
        required=True,
        error_messages={
            "required": "Member access level is required",
        },
    )

    domain_request_permission_admin = forms.ChoiceField(
        label=mark_safe(f"Select permission {required_star}"),  # nosec
        choices=[
            (UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS.value, "View all requests"),
            (UserPortfolioPermissionChoices.EDIT_REQUESTS.value, "View all requests plus create requests"),
        ],
        widget=forms.RadioSelect,
        required=False,
        error_messages={
            "required": "Admin domain request permission is required",
        },
    )

    member_permission_admin = forms.ChoiceField(
        label=mark_safe(f"Select permission {required_star}"),  # nosec
        choices=[
            (UserPortfolioPermissionChoices.VIEW_MEMBERS.value, "View all members"),
            (UserPortfolioPermissionChoices.EDIT_MEMBERS.value, "View all members plus manage members"),
        ],
        widget=forms.RadioSelect,
        required=False,
        error_messages={
            "required": "Admin member permission is required",
        },
    )

    domain_request_permission_member = forms.ChoiceField(
        # nosec B308 - required_star is a hardcoded HTML string
        label=mark_safe(f"Select permission {required_star}"),  # nosec
        choices=[
            (UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS.value, "View all requests"),
            (UserPortfolioPermissionChoices.EDIT_REQUESTS.value, "View all requests plus create requests"),
            ("no_access", "No access"),
        ],
        widget=forms.RadioSelect,
        required=False,
        error_messages={
            "required": "Basic member permission is required",
        },
    )

    # Tracks what form elements are required for a given role choice
    ROLE_REQUIRED_FIELDS = {
        UserPortfolioRoleChoices.ORGANIZATION_ADMIN: [
            "domain_request_permission_admin",
            "member_permission_admin",
        ],
        UserPortfolioRoleChoices.ORGANIZATION_MEMBER: [
            "domain_request_permission_member",
        ],
    }

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        if instance:
            self.instance = instance
            self.initial = self.map_instance_to_form(self.instance)
        # Adds a <p> description beneath each role option
        self.fields["role"].descriptions = {
            "organization_admin": UserPortfolioRoleChoices.get_role_description(
                UserPortfolioRoleChoices.ORGANIZATION_ADMIN
            ),
            "organization_member": UserPortfolioRoleChoices.get_role_description(
                UserPortfolioRoleChoices.ORGANIZATION_MEMBER
            ),
        }

    def clean(self):
        """
        Validates form data based on selected role and its required fields.

        Since form fields are dynamically shown/hidden via JavaScript based on role selection,
        we only validate fields that are relevant to the selected role:
        - organization_admin: ["member_permission_admin", "domain_request_permission_admin"]
        - organization_member: ["domain_request_permission_member"]
        This ensures users aren't required to fill out hidden fields and maintains
        proper validation based on their role selection.

        NOTE: This page uses ROLE_REQUIRED_FIELDS for the aforementioned mapping.
        Raises:
            ValueError: If ROLE_REQUIRED_FIELDS references a non-existent form field
        """
        cleaned_data = super().clean()
        role = cleaned_data.get("role")

        # Get required fields for the selected role.
        # Then validate all required fields for the role.
        required_fields = self.ROLE_REQUIRED_FIELDS.get(role, [])
        for field_name in required_fields:
            # Helpful error for if this breaks
            if field_name not in self.fields:
                raise ValueError(f"ROLE_REQUIRED_FIELDS referenced a non-existent field: {field_name}.")

            if not cleaned_data.get(field_name):
                self.add_error(field_name, self.fields.get(field_name).error_messages.get("required"))

        return cleaned_data

    def save(self):
        """Save the form data to the instance"""
        self.instance = self.map_cleaned_data_to_instance(self.cleaned_data, self.instance)
        self.instance.save()
        return self.instance

    def map_instance_to_form(self, instance):
        """
        Maps user instance to form fields, handling roles and permissions.

        Determines:
        - User's role (admin vs member)
        - Domain request permissions (EDIT_REQUESTS, VIEW_ALL_REQUESTS, or "no_access")
        - Member management permissions (EDIT_MEMBERS or VIEW_MEMBERS)

        Returns form data dictionary with appropriate permission levels based on user role:
        {
            "role": "organization_admin" or "organization_member",
            "member_permission_admin": permission level if admin,
            "domain_request_permission_admin": permission level if admin,
            "domain_request_permission_member": permission level if member
        }
        """
        if not instance:
            return {}

        # Function variables
        form_data = {}
        is_admin = UserPortfolioRoleChoices.ORGANIZATION_ADMIN in instance.roles if instance.roles else False
        perms = UserPortfolioPermission.get_portfolio_permissions(instance.roles, instance.additional_permissions)

        # Get role
        role = UserPortfolioRoleChoices.ORGANIZATION_MEMBER
        if is_admin:
            role = UserPortfolioRoleChoices.ORGANIZATION_ADMIN

        # Get domain request permission level
        domain_request_permission = None
        if UserPortfolioPermissionChoices.EDIT_REQUESTS in perms:
            domain_request_permission = UserPortfolioPermissionChoices.EDIT_REQUESTS
        elif UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS in perms:
            domain_request_permission = UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS

        # Get member permission level
        member_permission = None
        if UserPortfolioPermissionChoices.EDIT_MEMBERS in perms:
            member_permission = UserPortfolioPermissionChoices.EDIT_MEMBERS
        elif UserPortfolioPermissionChoices.VIEW_MEMBERS in perms:
            member_permission = UserPortfolioPermissionChoices.VIEW_MEMBERS

        # Build form data based on role.
        form_data = {
            "role": role,
            "member_permission_admin": member_permission.value if is_admin else None,
            "domain_request_permission_admin": domain_request_permission.value if is_admin else None,
            "domain_request_permission_member": domain_request_permission.value if not is_admin else None,
        }

        # Edgecase: Member uses a special form value for None called "no_access". This ensures a form selection.
        if domain_request_permission is None and not is_admin:
            form_data["domain_request_permission_member"] = "no_access"

        return form_data

    def map_cleaned_data_to_instance(self, cleaned_data, instance):
        """
        Maps cleaned data to a member instance, setting roles and permissions.

        Additional permissions logic:
        - For org admins: Adds domain request and member admin permissions if selected
        - For other roles: Adds domain request member permissions if not 'no_access'
        - Automatically adds VIEW permissions when EDIT permissions are granted
        - Filters out permissions already granted by base role

        Args:
            cleaned_data (dict): Cleaned data containing role and permission choices
            instance: Instance to update

        Returns:
            instance: Updated instance
        """
        role = cleaned_data.get("role")
        member_permission_admin = cleaned_data.get("member_permission_admin")
        domain_request_permission_admin = cleaned_data.get("domain_request_permission_admin")
        domain_request_permission_member = cleaned_data.get("domain_request_permission_member")

        # Handle roles
        instance.roles = [role]

        # Handle additional_permissions
        additional_permissions = set()
        if role == UserPortfolioRoleChoices.ORGANIZATION_ADMIN:
            if domain_request_permission_admin:
                additional_permissions.add(domain_request_permission_admin)

            if member_permission_admin:
                additional_permissions.add(member_permission_admin)
        else:
            if domain_request_permission_member and domain_request_permission_member != "no_access":
                additional_permissions.add(domain_request_permission_member)

        # Handle EDIT permissions (should be accompanied with a view permission)
        if UserPortfolioPermissionChoices.EDIT_MEMBERS in additional_permissions:
            additional_permissions.add(UserPortfolioPermissionChoices.VIEW_MEMBERS)

        if UserPortfolioPermissionChoices.EDIT_REQUESTS in additional_permissions:
            additional_permissions.add(UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS)

        # Only set unique permissions not already defined in the base role
        role_permissions = UserPortfolioPermission.get_portfolio_permissions(instance.roles, [], get_list=False)
        instance.additional_permissions = list(additional_permissions - role_permissions)
        return instance


class NewMemberForm(BasePortfolioMemberForm):
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

    def __init__(self, *args, **kwargs):
        self.portfolio = kwargs.pop("portfolio", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        # Lowercase the value of the 'email' field
        email_value = cleaned_data.get("email")
        if email_value:
            cleaned_data["email"] = email_value.lower()

        if email_value:
            # Check if user is already a member
            if UserPortfolioPermission.objects.filter(user__email=email_value, portfolio=self.portfolio).exists():
                self.add_error("email", "User is already a member of this portfolio.")

            if PortfolioInvitation.objects.filter(email=email_value, portfolio=self.portfolio).exists():
                self.add_error("email", "An invitation already exists for this user.")
        ##########################################
        # TODO: #3019
        # (invite new member)
        ##########################################
        # Check for an existing user (if there isn't any, send an invite)
        # if email_value:
        #     try:
        #         existingUser = User.objects.get(email=email_value)
        #     except User.DoesNotExist:
        #         raise forms.ValidationError("User with this email does not exist.")
        return cleaned_data

    def map_cleaned_data_to_instance(self, cleaned_data, instance):
        """Override of the base class to add portfolio and email."""
        instance = super().map_cleaned_data_to_instance(cleaned_data, instance)
        email = cleaned_data.get("email")
        if email and isinstance(email, str):
            email = email.lower()
        instance.email = email
        instance.portfolio = self.portfolio
        return instance
