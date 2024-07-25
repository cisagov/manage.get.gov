"""Forms for portfolio."""

import logging
from django import forms
from django.core.validators import RegexValidator

from ..models import DomainInformation, Portfolio

logger = logging.getLogger(__name__)


class PortfolioOrgAddressForm(forms.ModelForm):
    """Form for updating the portfolio org mailing address."""

    zipcode = forms.CharField(
        label="Zip code",
        validators=[
            RegexValidator(
                "^[0-9]{5}(?:-[0-9]{4})?$|^$",
                message="Enter a zip code in the required format, like 12345 or 12345-6789.",
            )
        ],
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

        # self.is_federal = self.instance.generic_org_type == DomainRequest.OrganizationChoices.FEDERAL
        # self.is_tribal = self.instance.generic_org_type == DomainRequest.OrganizationChoices.TRIBAL

        # field_to_disable = None
        # if self.is_federal:
        #     field_to_disable = "federal_agency"
        # elif self.is_tribal:
        #     field_to_disable = "organization_name"

        # if field_to_disable is not None:
        #     DomainHelper.disable_field(self.fields[field_to_disable], disable_required=True)

    # def save(self, commit=True):
    #     """Override the save() method of the BaseModelForm."""
    #     if self.has_changed():

    #         if self.is_federal and not self._field_unchanged("federal_agency"):
    #             raise ValueError("federal_agency cannot be modified when the generic_org_type is federal")
    #         elif self.is_tribal and not self._field_unchanged("organization_name"):
    #             raise ValueError("organization_name cannot be modified when the generic_org_type is tribal")

    #     else:
    #         super().save()

    # def _field_unchanged(self, field_name) -> bool:
    #     """
    #     Checks if a specified field has not changed between the old value
    #     and the new value.

    #     The old value is grabbed from self.initial.
    #     The new value is grabbed from self.cleaned_data.
    #     """
    #     old_value = self.initial.get(field_name, None)
    #     new_value = self.cleaned_data.get(field_name, None)
    #     return old_value == new_value