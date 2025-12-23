"""Forms for portfolio."""

import logging
from django import forms
from django.core.validators import RegexValidator
from django.core.validators import MaxLengthValidator

from registrar.forms.utility.combobox import ComboboxWidget
from registrar.models import (
    PortfolioInvitation,
    UserPortfolioPermission,
    DomainInformation,
    Portfolio,
    SeniorOfficial,
)
from registrar.models.utility.portfolio_helper import (
    UserPortfolioPermissionChoices,
    UserPortfolioRoleChoices,
    get_domain_requests_description_display,
    get_domain_requests_display,
    get_domains_description_display,
    get_domains_display,
    get_members_description_display,
    get_members_display,
    get_portfolio_invitation_associations,
)

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
    state_territory = forms.ChoiceField(
        label="State, territory, or military post",
        required=True,
        choices=DomainInformation.StateTerritoryChoices.choices,  # type: ignore[misc]
        error_messages={
            "required": ("Select the state, territory, or military post where your organization is located.")
        },
        widget=ComboboxWidget(attrs={"required": True}),
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
            "zipcode": {"required": "Enter a 5-digit or 9-digit zip code, like 12345 or 12345-6789."},
        }
        widgets = {
            "address_line1": forms.TextInput,
            "address_line2": forms.TextInput,
            "city": forms.TextInput,
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
    """Base form for the PortfolioMemberForm and PortfolioInvitedMemberForm"""

    # The label for each of these has a red "required" star. We can just embed that here for simplicity.
    required_star = '<abbr class="usa-hint usa-hint--required" title="required">*</abbr>'
    role = forms.ChoiceField(
        choices=[
            # Uses .value because the choice has a different label (on /admin)
            (UserPortfolioRoleChoices.ORGANIZATION_ADMIN.value, "Organization admin"),
            (UserPortfolioRoleChoices.ORGANIZATION_MEMBER.value, "Basic"),
        ],
        widget=forms.RadioSelect,
        required=True,
        error_messages={
            "required": "Select the role you would like to grant this member.",
        },
    )

    domain_permissions = forms.ChoiceField(
        choices=[
            (
                UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS.value,
                get_domains_display(UserPortfolioRoleChoices.ORGANIZATION_MEMBER, None),
            ),
            (
                UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS.value,
                get_domains_display(
                    UserPortfolioRoleChoices.ORGANIZATION_MEMBER, [UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS]
                ),
            ),
        ],
        widget=forms.RadioSelect,
        required=False,
        initial=UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS.value,
        error_messages={
            "required": "Domain permission is required.",
        },
    )

    domain_request_permissions = forms.ChoiceField(
        choices=[
            ("no_access", get_domain_requests_display(UserPortfolioRoleChoices.ORGANIZATION_MEMBER, None)),
            (
                UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS.value,
                get_domain_requests_display(
                    UserPortfolioRoleChoices.ORGANIZATION_MEMBER, [UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS]
                ),
            ),
            (
                UserPortfolioPermissionChoices.EDIT_REQUESTS.value,
                get_domain_requests_display(
                    UserPortfolioRoleChoices.ORGANIZATION_MEMBER, [UserPortfolioPermissionChoices.EDIT_REQUESTS]
                ),
            ),
        ],
        widget=forms.RadioSelect,
        required=False,
        initial="no_access",
        error_messages={
            "required": "Domain request permission is required.",
        },
    )

    member_permissions = forms.ChoiceField(
        choices=[
            ("no_access", get_members_display(UserPortfolioRoleChoices.ORGANIZATION_MEMBER, None)),
            (
                UserPortfolioPermissionChoices.VIEW_MEMBERS.value,
                get_members_display(
                    UserPortfolioRoleChoices.ORGANIZATION_MEMBER, [UserPortfolioPermissionChoices.VIEW_MEMBERS]
                ),
            ),
        ],
        widget=forms.RadioSelect,
        required=False,
        initial="no_access",
        error_messages={
            "required": "Member permission is required.",
        },
    )

    # Tracks what form elements are required for a given role choice.
    # All of the fields included here have "required=False" by default as they are conditionally required.
    # see def clean() for more details.
    ROLE_REQUIRED_FIELDS = {
        UserPortfolioRoleChoices.ORGANIZATION_ADMIN: [],
        UserPortfolioRoleChoices.ORGANIZATION_MEMBER: [
            "domain_permissions",
            "member_permissions",
            "domain_request_permissions",
        ],
    }

    class Meta:
        model = None
        fields = ["roles", "additional_permissions"]

    def __init__(self, *args, **kwargs):
        """
        Override the form's initialization.

        Map existing model values to custom form fields.
        Update field descriptions.
        """
        super().__init__(*args, **kwargs)

        # Adds a <p> description beneath each option
        self.fields["domain_permissions"].descriptions = {
            UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS.value: get_domains_description_display(
                UserPortfolioRoleChoices.ORGANIZATION_MEMBER, None
            ),
            UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS.value: get_domains_description_display(
                UserPortfolioRoleChoices.ORGANIZATION_MEMBER, [UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS]
            ),
        }
        self.fields["domain_request_permissions"].descriptions = {
            UserPortfolioPermissionChoices.EDIT_REQUESTS.value: (
                get_domain_requests_description_display(
                    UserPortfolioRoleChoices.ORGANIZATION_MEMBER, [UserPortfolioPermissionChoices.EDIT_REQUESTS]
                )
            ),
            UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS.value: (
                get_domain_requests_description_display(
                    UserPortfolioRoleChoices.ORGANIZATION_MEMBER, [UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS]
                )
            ),
            "no_access": get_domain_requests_description_display(UserPortfolioRoleChoices.ORGANIZATION_MEMBER, None),
        }
        self.fields["member_permissions"].descriptions = {
            UserPortfolioPermissionChoices.VIEW_MEMBERS.value: get_members_description_display(
                UserPortfolioRoleChoices.ORGANIZATION_MEMBER, [UserPortfolioPermissionChoices.VIEW_MEMBERS]
            ),
            "no_access": get_members_description_display(UserPortfolioRoleChoices.ORGANIZATION_MEMBER, None),
        }

        # Map model instance values to custom form fields
        if self.instance:
            self.map_instance_to_initial()

    def clean(self):
        """Validates form data based on selected role and its required fields.
        Updates roles and additional_permissions in cleaned_data so they can be properly
        mapped to the model.
        """
        cleaned_data = super().clean()
        role = cleaned_data.get("role")

        # handle role
        cleaned_data["roles"] = [role] if role else []

        # Get required fields for the selected role. Then validate all required fields for the role.
        required_fields = self.ROLE_REQUIRED_FIELDS.get(role, [])
        for field_name in required_fields:
            # Helpful error for if this breaks
            if field_name not in self.fields:
                raise ValueError(f"ROLE_REQUIRED_FIELDS referenced a non-existent field: {field_name}.")

            if not cleaned_data.get(field_name):
                self.add_error(field_name, self.fields.get(field_name).error_messages.get("required"))

        # Edgecase: Member uses a special form value for None called "no_access".
        if cleaned_data.get("domain_request_permissions") == "no_access":
            cleaned_data["domain_request_permissions"] = None

        # Edgecase: Member uses a special form value for None called "no_access".
        if cleaned_data.get("member_permissions") == "no_access":
            cleaned_data["member_permissions"] = None

        # Handle additional_permissions
        valid_fields = self.ROLE_REQUIRED_FIELDS.get(role, [])
        additional_permissions = {cleaned_data.get(field) for field in valid_fields if cleaned_data.get(field)}

        # Handle EDIT permissions (should be accompanied with a view permission)
        if UserPortfolioPermissionChoices.EDIT_MEMBERS in additional_permissions:
            additional_permissions.add(UserPortfolioPermissionChoices.VIEW_MEMBERS)

        if UserPortfolioPermissionChoices.EDIT_REQUESTS in additional_permissions:
            additional_permissions.add(UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS)

        # Only set unique permissions not already defined in the base role
        role_permissions = UserPortfolioPermission.get_portfolio_permissions(cleaned_data["roles"], [], get_list=False)
        cleaned_data["additional_permissions"] = list(additional_permissions - role_permissions)

        return cleaned_data

    def map_instance_to_initial(self):
        """
        Maps self.instance to self.initial, handling roles and permissions.
        Updates self.initial dictionary with appropriate permission levels based on user role:
        {
            "role": "organization_admin" or "organization_member",
            "member_permission_admin": permission level if admin,
            "domain_request_permission_admin": permission level if admin,
            "domain_request_permissions": permission level if member
        }
        """
        if self.initial is None:
            self.initial = {}
        # Function variables
        perms = UserPortfolioPermission.get_portfolio_permissions(
            self.instance.roles, self.instance.additional_permissions, get_list=False
        )
        # Get the available options for roles, domains, and member.
        roles = [
            UserPortfolioRoleChoices.ORGANIZATION_ADMIN,
            UserPortfolioRoleChoices.ORGANIZATION_MEMBER,
        ]
        domain_request_perms = [
            UserPortfolioPermissionChoices.EDIT_REQUESTS,
            UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS,
        ]
        domain_perms = [
            UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS,
            UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS,
        ]
        member_perms = [
            UserPortfolioPermissionChoices.VIEW_MEMBERS,
        ]

        # Build form data based on role (which options are available).
        # Get which one should be "selected" by assuming that EDIT takes precedence over view,
        # and ADMIN takes precedence over MEMBER.
        roles = self.instance.roles or []
        selected_role = next((role for role in roles if role in roles), None)
        self.initial["role"] = selected_role
        is_member = selected_role == UserPortfolioRoleChoices.ORGANIZATION_MEMBER
        if is_member:
            # Edgecase: Member and domain request use a special form value for None called "no_access".
            # This ensures a form selection.
            selected_domain_permission = next(
                (perm for perm in domain_perms if perm in perms),
                UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS.value,
            )
            selected_domain_request_permission = next(
                (perm for perm in domain_request_perms if perm in perms), "no_access"
            )
            selected_member_permission = next((perm for perm in member_perms if perm in perms), "no_access")
            self.initial["domain_request_permissions"] = selected_domain_request_permission
            self.initial["domain_permissions"] = selected_domain_permission
            self.initial["member_permissions"] = selected_member_permission

    def is_change_from_member_to_admin(self) -> bool:
        """
        Checks if the roles have changed from not containing ORGANIZATION_ADMIN
        to containing ORGANIZATION_ADMIN.
        """
        previous_roles = set(self.initial.get("roles", []))  # Initial roles before change
        new_roles = set(self.cleaned_data.get("roles", []))  # New roles after change

        return (
            UserPortfolioRoleChoices.ORGANIZATION_ADMIN not in previous_roles
            and UserPortfolioRoleChoices.ORGANIZATION_ADMIN in new_roles
        )

    def is_change_from_admin_to_member(self) -> bool:
        """
        Checks if the roles have changed from containing ORGANIZATION_ADMIN
        to not containing ORGANIZATION_ADMIN.
        """
        previous_roles = set(self.initial.get("roles", []))  # Initial roles before change
        new_roles = set(self.cleaned_data.get("roles", []))  # New roles after change

        return (
            UserPortfolioRoleChoices.ORGANIZATION_ADMIN in previous_roles
            and UserPortfolioRoleChoices.ORGANIZATION_ADMIN not in new_roles
        )

    def is_change(self) -> bool:
        """
        Determines if the form has changed by comparing the initial data
        with the submitted cleaned data.

        Returns:
            bool: True if the form has changed, False otherwise.
        """
        # Compare role values
        previous_roles = set(self.initial.get("roles", []))
        new_roles = set(self.cleaned_data.get("roles", []))

        # Compare additional permissions values
        previous_permissions = set(self.initial.get("additional_permissions") or [])
        new_permissions = set(self.cleaned_data.get("additional_permissions") or [])

        return previous_roles != new_roles or previous_permissions != new_permissions


class PortfolioMemberForm(BasePortfolioMemberForm):
    """
    Form for updating a portfolio member.
    """

    class Meta:
        model = UserPortfolioPermission
        fields = ["roles", "additional_permissions"]

    def clean(self):
        """
        Override of clean to ensure that the user isn't removing themselves
        if they're the only portfolio admin
        """
        super().clean()
        role = self.cleaned_data.get("role")
        if self.instance and hasattr(self.instance, "user") and hasattr(self.instance, "portfolio"):
            if role and self.instance.user.is_only_admin_of_portfolio(self.instance.portfolio):
                # This is how you associate a validation error to a particular field.
                # The alternative is to do this in clean_role, but execution order matters.
                raise forms.ValidationError(
                    {
                        "role": forms.ValidationError(
                            "You can't change your member role because you're "
                            "the only admin for this organization. "
                            "To change your role, you'll need to add another admin."
                        )
                    }
                )


class PortfolioInvitedMemberForm(BasePortfolioMemberForm):
    """
    Form for updating a portfolio invited member.
    """

    class Meta:
        model = PortfolioInvitation
        fields = ["roles", "additional_permissions"]


class PortfolioNewMemberForm(BasePortfolioMemberForm):
    """
    Form for adding a portfolio invited member.
    """

    email = forms.EmailField(
        label="Email",
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

    def _post_clean(self):
        """
        Override _post_clean to customize model validation errors.
        This runs after form clean is complete, but before the errors are displayed.
        """
        try:
            super()._post_clean()
            self.instance.clean()
        except forms.ValidationError as e:
            override_error = False
            if hasattr(e, "code"):
                field = "email" if "email" in self.fields else None
                if e.code == "has_existing_permissions":
                    existing_permissions, existing_invitations = get_portfolio_invitation_associations(self.instance)

                    same_portfolio_for_permissions = existing_permissions.exclude(portfolio=self.instance.portfolio)
                    same_portfolio_for_invitations = existing_invitations.exclude(portfolio=self.instance.portfolio)
                    if same_portfolio_for_permissions.exists() or same_portfolio_for_invitations.exists():
                        self.add_error(
                            field, f"{self.instance.email} is already a member of another .gov organization."
                        )
                    override_error = True
                elif e.code == "has_existing_invitations":
                    self.add_error(
                        field, f"{self.instance.email} has already been invited to another .gov organization."
                    )
                    override_error = True

            # Errors denoted as "__all__" are special error types reserved for the model level clean function
            if override_error and "__all__" in self._errors:
                del self._errors["__all__"]
