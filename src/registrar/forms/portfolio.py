"""Forms for portfolio."""

import logging
from django import forms
from django.core.validators import RegexValidator
from django.core.validators import MaxLengthValidator

from registrar.models.user_portfolio_permission import UserPortfolioPermission

from ..models import DomainInformation, Portfolio, SeniorOfficial, User

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
    

class NewMemberForm(forms.ModelForm):
    admin_org_domain_request_permissions = forms.ChoiceField(
        label="Select permission",
        choices=[('view_only', 'View all requests'), ('view_and_create', 'View all requests plus create requests')], 
        widget=forms.RadioSelect, 
        required=True)
    admin_org_members_permissions = forms.ChoiceField(
        label="Select permission", choices=[('view_only', 'View all members'), ('view_and_create', 'View all members plus manage members')], widget=forms.RadioSelect, required=True)
    basic_org_domain_request_permissions = forms.ChoiceField(
        label="Select permission", choices=[('view_only', 'View all requests'), ('view_and_create', 'View all requests plus create requests'),('no_access', 'No access')], widget=forms.RadioSelect, required=True)
    
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
        required=True
    )

    class Meta:
        model = User
        fields = ['email'] #, 'grade', 'sport']

    def clean(self):
        cleaned_data = super().clean()

        # Lowercase the value of the 'email' field
        email_value = cleaned_data.get("email")
        if email_value:
            cleaned_data["email"] = email_value.lower()

        # Check for an existing user (if there isn't any, send an invite)
        if email_value:
            try:
                existingUser = User.objects.get(email=email_value)
            except existingUser.DoesNotExist:
                raise forms.ValidationError("User with this email does not exist.")
            
        # grade = cleaned_data.get('grade')
        # sport = cleaned_data.get('sport')

        # # Handle sport options based on grade
        # if grade == 'Junior':
        #     self.fields['sport'].choices = [('Basketball', 'Basketball'), ('Football', 'Football')]
        # elif grade == 'Varsity':
        #     self.fields['sport'].choices = [('Swimming', 'Swimming'), ('Tennis', 'Tennis')]

        # # Ensure both sport and grade are selected and valid
        # if not grade or not sport:
        #     raise forms.ValidationError("Both grade and sport must be selected.")

        return cleaned_data