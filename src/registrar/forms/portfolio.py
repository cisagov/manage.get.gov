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


class BasePortfolioMemberForm(forms.ModelForm):
    role = forms.ChoiceField(
        label="Select permission",
        choices=[
            (UserPortfolioRoleChoices.ORGANIZATION_ADMIN.value, "Admin Access"),
            (UserPortfolioRoleChoices.ORGANIZATION_MEMBER.value, "Basic Access")
        ],
        widget=forms.RadioSelect,
        required=True,
        error_messages={
            "required": "Member access level is required",
        },
    )
    # Permissions for admins
    domain_request_permissions_admin = forms.ChoiceField(
        label="Select permission",
        choices=[
            (UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS.value, "View all requests"),
            (UserPortfolioPermissionChoices.EDIT_REQUESTS.value, "Create and edit requests")
        ],
        widget=forms.RadioSelect,
        required=False,
        error_messages={
            "required": "Admin domain request permission is required",
        },
    )
    member_permissions_admin = forms.ChoiceField(
        label="Select permission",
        choices=[
            (UserPortfolioPermissionChoices.VIEW_MEMBERS.value, "View all members"),
            (UserPortfolioPermissionChoices.EDIT_MEMBERS.value, "Create and edit members")
        ],
        widget=forms.RadioSelect,
        required=False,
        error_messages={
            "required": "Admin member permission is required",
        },
    )
    domain_request_permissions_member = forms.ChoiceField(
        label="Select permission",
        choices=[
            (UserPortfolioPermissionChoices.VIEW_MEMBERS.value, "View all members"),
            (UserPortfolioPermissionChoices.EDIT_MEMBERS.value, "Create and edit members")
        ],
        widget=forms.RadioSelect,
        required=False,
        error_messages={
            "required": "Basic member permission is required",
        },
    )

    # this form dynamically shows/hides some fields, depending on what
    # was selected prior. This toggles which field is required or not.
    ROLE_REQUIRED_FIELDS = {
        UserPortfolioRoleChoices.ORGANIZATION_ADMIN: [
            "domain_request_permissions_admin",
            "member_permissions_admin",
        ],
        UserPortfolioRoleChoices.ORGANIZATION_MEMBER: [
            "domain_request_permissions_member",
        ],
    }

    def _map_instance_to_form(self, instance):
        """Maps model instance data to form fields"""
        if not instance:
            return {}
        mapped_data = {}
        # Map roles with priority for admin
        if instance.roles:
            if UserPortfolioRoleChoices.ORGANIZATION_ADMIN.value in instance.roles:
                mapped_data['role'] = UserPortfolioRoleChoices.ORGANIZATION_ADMIN.value
            else:
                mapped_data['role'] = UserPortfolioRoleChoices.ORGANIZATION_MEMBER.value

        perms = UserPortfolioPermission.get_portfolio_permissions(instance.roles, instance.additional_permissions)
        # Map permissions with priority for edit permissions
        if perms:
            if UserPortfolioPermissionChoices.EDIT_REQUESTS.value in perms:
                mapped_data['domain_request_permissions_admin'] = UserPortfolioPermissionChoices.EDIT_REQUESTS.value
            elif UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS.value in perms:
                mapped_data['domain_request_permissions_admin'] = UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS.value

            if UserPortfolioPermissionChoices.EDIT_MEMBERS.value in perms:
                mapped_data['member_permissions_admin'] = UserPortfolioPermissionChoices.EDIT_MEMBERS.value
            elif UserPortfolioPermissionChoices.VIEW_MEMBERS.value in perms:
                mapped_data['member_permissions_admin'] = UserPortfolioPermissionChoices.VIEW_MEMBERS.value
                
        return mapped_data

    def _map_form_to_instance(self, instance):
        """Maps form data to model instance"""
        if not self.is_valid():
            return

        role = self.cleaned_data.get("role")
        domain_request_permissions_member = self.cleaned_data.get("domain_request_permissions_member")
        domain_request_permissions_admin = self.cleaned_data.get('domain_request_permissions_admin')
        member_permissions_admin = self.cleaned_data.get('member_permissions_admin')

        instance.roles = [role]
        additional_permissions = []
        if domain_request_permissions_member:
            additional_permissions.append(domain_request_permissions_member)
        elif domain_request_permissions_admin:
            additional_permissions.append(domain_request_permissions_admin)
        
        if member_permissions_admin:
            additional_permissions.append(member_permissions_admin)

        instance.additional_permissions = additional_permissions
        return instance

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")

        # Get required fields for the selected role.
        # Then validate all required fields for the role.
        required_fields = self.ROLE_REQUIRED_FIELDS.get(role, [])
        for field_name in required_fields:
            if not cleaned_data.get(field_name):
                self.add_error(
                    field_name,
                    self.fields.get(field_name).error_messages.get("required")
                )

        return cleaned_data


class PortfolioMemberForm(BasePortfolioMemberForm):
    """
    Form for updating a portfolio member.
    """
    class Meta:
        model = UserPortfolioPermission
        fields = [
            "roles",
            "additional_permissions",
        ]
    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].descriptions = {
            "organization_admin": UserPortfolioRoleChoices.get_role_description(UserPortfolioRoleChoices.ORGANIZATION_ADMIN),
            "organization_member": UserPortfolioRoleChoices.get_role_description(UserPortfolioRoleChoices.ORGANIZATION_MEMBER)
        }
        self.instance = instance
        self.initial = self._map_instance_to_form(self.instance)
    
    def save(self):
        """Save form data to instance"""
        if not self.instance:
            self.instance = self.Meta.model()
        self._map_form_to_instance(self.instance)
        self.instance.save()
        return self.instance


class PortfolioInvitedMemberForm(BasePortfolioMemberForm):
    """
    Form for updating a portfolio invited member.
    """

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
        widget=forms.RadioSelect(attrs={"class": "usa-radio__input  usa-radio__input--tile"}),
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
            "required": "Admin domain request permission is required",
        },
    )
    admin_org_members_permissions = forms.ChoiceField(
        label="Select permission",
        choices=[("view_only", "View all members"), ("view_and_create", "View all members plus manage members")],
        widget=forms.RadioSelect,
        required=True,
        error_messages={
            "required": "Admin member permission is required",
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
        model = User
        fields = ["email"]

    def clean(self):
        cleaned_data = super().clean()

        # Lowercase the value of the 'email' field
        email_value = cleaned_data.get("email")
        if email_value:
            cleaned_data["email"] = email_value.lower()

        ##########################################
        # TODO: future ticket
        # (invite new member)
        ##########################################
        # Check for an existing user (if there isn't any, send an invite)
        # if email_value:
        #     try:
        #         existingUser = User.objects.get(email=email_value)
        #     except User.DoesNotExist:
        #         raise forms.ValidationError("User with this email does not exist.")

        member_access_level = cleaned_data.get("member_access_level")

        # Intercept the error messages so that we don't validate hidden inputs
        if not member_access_level:
            # If no member access level has been selected, delete error messages
            # for all hidden inputs (which is everything except the e-mail input
            # and member access selection)
            for field in self.fields:
                if field in self.errors and field != "email" and field != "member_access_level":
                    del self.errors[field]
            return cleaned_data

        basic_dom_req_error = "basic_org_domain_request_permissions"
        admin_dom_req_error = "admin_org_domain_request_permissions"
        admin_member_error = "admin_org_members_permissions"

        if member_access_level == "admin" and basic_dom_req_error in self.errors:
            # remove the error messages pertaining to basic permission inputs
            del self.errors[basic_dom_req_error]
        elif member_access_level == "basic":
            # remove the error messages pertaining to admin permission inputs
            if admin_dom_req_error in self.errors:
                del self.errors[admin_dom_req_error]
            if admin_member_error in self.errors:
                del self.errors[admin_member_error]
        return cleaned_data
