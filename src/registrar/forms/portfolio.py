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


class BasePortfolioMemberForm(forms.Form):
    """Base form for the PortfolioMemberForm and PortfolioInvitedMemberForm"""

    # The label for each of these has a red "required" star. We can just embed that here for simplicity.
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

    # Tracks what form elements are required for a given role choice.
    # All of the fields included here have "required=False" by default as they are conditionally required.
    # see def clean() for more details.
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
        """Validates form data based on selected role and its required fields."""
        cleaned_data = super().clean()
        role = cleaned_data.get("role")

        # Get required fields for the selected role. Then validate all required fields for the role.
        required_fields = self.ROLE_REQUIRED_FIELDS.get(role, [])
        for field_name in required_fields:
            # Helpful error for if this breaks
            if field_name not in self.fields:
                raise ValueError(f"ROLE_REQUIRED_FIELDS referenced a non-existent field: {field_name}.")

            if not cleaned_data.get(field_name):
                self.add_error(field_name, self.fields.get(field_name).error_messages.get("required"))

        # Edgecase: Member uses a special form value for None called "no_access".
        if cleaned_data.get("domain_request_permission_member") == "no_access":
            cleaned_data["domain_request_permission_member"] = None

        return cleaned_data

    def save(self):
        """Save the form data to the instance"""
        self.instance = self.map_cleaned_data_to_instance(self.cleaned_data, self.instance)
        self.instance.save()
        return self.instance

    # Explanation of how map_instance_to_form / map_cleaned_data_to_instance work:
    # map_instance_to_form => called on init to set self.initial.
    # Converts the incoming object (usually PortfolioInvitation or UserPortfolioPermission)
    # into a dictionary representation for the form to use automatically.

    # map_cleaned_data_to_instance => called on save() to save the instance to the db.
    # Takes the self.cleaned_data dict, and converts this dict back to the object.

    def map_instance_to_form(self, instance):
        """
        Maps user instance to form fields, handling roles and permissions.
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
        perms = UserPortfolioPermission.get_portfolio_permissions(
            instance.roles, instance.additional_permissions, get_list=False
        )

        # Explanation of this logic pattern: we can only display one item in the list at a time.
        # But how do we determine what is most important to display in a list? Order-based hierarchy.
        # Example: print(instance.roles) => (output) ["organization_admin", "organization_member"]
        # If we can only pick one item in this list, we should pick organization_admin.

        # Get role
        roles = [UserPortfolioRoleChoices.ORGANIZATION_ADMIN, UserPortfolioRoleChoices.ORGANIZATION_MEMBER]
        role = next((role for role in roles if role in instance.roles), None)
        is_admin = role == UserPortfolioRoleChoices.ORGANIZATION_ADMIN

        # Get domain request permission level
        # First we get permissions we expect to display (ordered hierarchically).
        # Then we check if this item exists in the list and return the first instance of it.
        domain_permissions = [
            UserPortfolioPermissionChoices.EDIT_REQUESTS,
            UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS,
        ]
        domain_request_permission = next((perm for perm in domain_permissions if perm in perms), None)

        # Get member permission level.
        member_permissions = [UserPortfolioPermissionChoices.EDIT_MEMBERS, UserPortfolioPermissionChoices.VIEW_MEMBERS]
        member_permission = next((perm for perm in member_permissions if perm in perms), None)

        # Build form data based on role.
        form_data = {
            "role": role,
            "member_permission_admin": getattr(member_permission, "value", None) if is_admin else None,
            "domain_request_permission_admin": getattr(domain_request_permission, "value", None) if is_admin else None,
            "domain_request_permission_member": (
                getattr(domain_request_permission, "value", None) if not is_admin else None
            ),
        }

        # Edgecase: Member uses a special form value for None called "no_access". This ensures a form selection.
        if domain_request_permission is None and not is_admin:
            form_data["domain_request_permission_member"] = "no_access"

        return form_data

    def map_cleaned_data_to_instance(self, cleaned_data, instance):
        """
        Maps cleaned data to a member instance, setting roles and permissions.
        Args:
            cleaned_data (dict): Cleaned data containing role and permission choices
            instance: Instance to update

        Returns:
            instance: Updated instance
        """
        role = cleaned_data.get("role")

        # Handle roles
        instance.roles = [role]

        # Handle additional_permissions
        valid_fields = self.ROLE_REQUIRED_FIELDS.get(role, [])
        additional_permissions = {cleaned_data.get(field) for field in valid_fields if cleaned_data.get(field)}

        # Handle EDIT permissions (should be accompanied with a view permission)
        if UserPortfolioPermissionChoices.EDIT_MEMBERS in additional_permissions:
            additional_permissions.add(UserPortfolioPermissionChoices.VIEW_MEMBERS)

        if UserPortfolioPermissionChoices.EDIT_REQUESTS in additional_permissions:
            additional_permissions.add(UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS)

        # Only set unique permissions not already defined in the base role
        role_permissions = UserPortfolioPermission.get_portfolio_permissions(instance.roles, [], get_list=False)
        instance.additional_permissions = list(additional_permissions - role_permissions)
        return instance
