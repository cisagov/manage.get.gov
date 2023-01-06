from __future__ import annotations  # allows forward references in annotations
import logging

from django import forms

from registrar.models import Contact, DomainApplication, Domain

logger = logging.getLogger(__name__)


class RegistrarForm(forms.Form):
    """
    A common set of methods and configuration.

    The registrar's domain application is several pages of "steps".
    Each step is an HTML form containing one or more Django "forms".

    Subclass this class to create new forms.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super(RegistrarForm, self).__init__(*args, **kwargs)

    def to_database(self, obj: DomainApplication | Contact):
        """
        Adds this form's cleaned data to `obj` and saves `obj`.

        Does nothing if form is not valid.
        """
        if not self.is_valid():
            return
        for name, value in self.cleaned_data.items():
            setattr(obj, name, value)
        obj.save()

    @classmethod
    def from_database(cls, obj: DomainApplication | Contact | None):
        """Returns a dict of form field values gotten from `obj`."""
        if obj is None:
            return {}
        return {
            name: getattr(obj, name) for name in cls.declared_fields.keys()
        }  # type: ignore


class OrganizationTypeForm(RegistrarForm):
    organization_type = forms.ChoiceField(
        required=True,
        choices=DomainApplication.OrganizationChoices.choices,
        widget=forms.RadioSelect,
    )


class OrganizationFederalForm(RegistrarForm):
    federal_type = forms.ChoiceField(
        choices=DomainApplication.BranchChoices.choices,
        widget=forms.RadioSelect,
    )


class OrganizationElectionForm(RegistrarForm):
    is_election_board = forms.BooleanField(
        widget=forms.RadioSelect(
            choices=[
                (True, "Yes"),
                (False, "No"),
            ],
        ),
    )


class OrganizationContactForm(RegistrarForm):
    # for federal agencies we also want to know the top-level agency.
    federal_agency = forms.ChoiceField(
        label="Federal agency",
        # not required because this field won't be filled out unless
        # it is a federal agency.
        required=False,
        choices=DomainApplication.AGENCY_CHOICES,
    )
    organization_name = forms.CharField(label="Organization Name")
    address_line1 = forms.CharField(label="Street address")
    address_line2 = forms.CharField(
        required=False,
        label="Street address line 2",
    )
    city = forms.CharField(label="City")
    state_territory = forms.ChoiceField(
        label="State, territory, or military post",
        choices=[("", "--Select--")] + DomainApplication.StateTerritoryChoices.choices,
    )
    zipcode = forms.CharField(label="ZIP code")
    urbanization = forms.CharField(
        required=False,
        label="Urbanization (Puerto Rico only)",
    )


class AuthorizingOfficialForm(RegistrarForm):
    def to_database(self, obj):
        if not self.is_valid():
            return
        contact = getattr(obj, "authorizing_official", None)
        if contact is not None:
            super().to_database(contact)
        else:
            contact = Contact()
            super().to_database(contact)
            obj.authorizing_official = contact
            obj.save()

    @classmethod
    def from_database(cls, obj):
        contact = getattr(obj, "authorizing_official", None)
        return super().from_database(contact)

    first_name = forms.CharField(label="First name/given name")
    middle_name = forms.CharField(
        required=False,
        label="Middle name (optional)",
    )
    last_name = forms.CharField(label="Last name/family name")
    title = forms.CharField(label="Title or role in your organization")
    email = forms.EmailField(label="Email")
    phone = forms.CharField(label="Phone")


class CurrentSitesForm(RegistrarForm):
    def to_database(self, obj):
        if not self.is_valid():
            return
        obj.save()
        normalized = Domain.normalize(self.cleaned_data["current_site"], blank=True)
        if normalized:
            # TODO: ability to update existing records
            obj.current_websites.create(website=normalized)

    @classmethod
    def from_database(cls, obj):
        current_website = obj.current_websites.first()
        if current_website is not None:
            return {"current_site": current_website.website}
        else:
            return {}

    current_site = forms.CharField(
        required=False,
        label="Enter your organization’s public website, if you have one. For example, "
        "www.city.com.",
    )


class DotGovDomainForm(RegistrarForm):
    def to_database(self, obj):
        if not self.is_valid():
            return
        normalized = Domain.normalize(
            self.cleaned_data["requested_domain"], "gov", blank=True
        )
        if normalized:
            requested_domain = getattr(obj, "requested_domain", None)
            if requested_domain is not None:
                requested_domain.name = normalized
                requested_domain.save()
            else:
                requested_domain = Domain.objects.create(name=normalized)
                obj.requested_domain = requested_domain
                obj.save()

        obj.save()
        normalized = Domain.normalize(
            self.cleaned_data["alternative_domain"], "gov", blank=True
        )
        if normalized:
            # TODO: ability to update existing records
            obj.alternative_domains.create(website=normalized)

    @classmethod
    def from_database(cls, obj):
        values = {}
        requested_domain = getattr(obj, "requested_domain", None)
        if requested_domain is not None:
            values["requested_domain"] = requested_domain.sld

        alternative_domain = obj.alternative_domains.first()
        if alternative_domain is not None:
            values["alternative_domain"] = alternative_domain.sld

        return values

    requested_domain = forms.CharField(label="What .gov domain do you want?")
    alternative_domain = forms.CharField(
        required=False,
        label="Are there other domains you’d like if we can’t give you your first "
        "choice? Entering alternative domains is optional.",
    )


class PurposeForm(RegistrarForm):
    purpose = forms.CharField(label="Purpose", widget=forms.Textarea())


class YourContactForm(RegistrarForm):
    def to_database(self, obj):
        if not self.is_valid():
            return
        contact = getattr(obj, "submitter", None)
        if contact is not None:
            super().to_database(contact)
        else:
            contact = Contact()
            super().to_database(contact)
            obj.submitter = contact
            obj.save()

    @classmethod
    def from_database(cls, obj):
        contact = getattr(obj, "submitter", None)
        return super().from_database(contact)

    first_name = forms.CharField(label="First name/given name")
    middle_name = forms.CharField(
        required=False,
        label="Middle name (optional)",
    )
    last_name = forms.CharField(label="Last name/family name")
    title = forms.CharField(label="Title or role in your organization")
    email = forms.EmailField(label="Email")
    phone = forms.CharField(label="Phone")


class OtherContactsForm(RegistrarForm):
    def to_database(self, obj):
        if not self.is_valid():
            return
        obj.save()

        # TODO: ability to handle multiple contacts
        contact = obj.other_contacts.filter(email=self.cleaned_data["email"]).first()
        if contact is not None:
            super().to_database(contact)
        else:
            contact = Contact()
            super().to_database(contact)
            obj.other_contacts.add(contact)

    @classmethod
    def from_database(cls, obj):
        other_contacts = obj.other_contacts.first()
        return super().from_database(other_contacts)

    first_name = forms.CharField(label="First name/given name")
    middle_name = forms.CharField(
        required=False,
        label="Middle name (optional)",
    )
    last_name = forms.CharField(label="Last name/family name")
    title = forms.CharField(label="Title or role in your organization")
    email = forms.EmailField(label="Email")
    phone = forms.CharField(label="Phone")


class SecurityEmailForm(RegistrarForm):
    security_email = forms.EmailField(
        required=False,
        label="Security email",
    )


class AnythingElseForm(RegistrarForm):
    anything_else = forms.CharField(
        required=False,
        label="Anything else we should know",
        widget=forms.Textarea(),
    )


class RequirementsForm(RegistrarForm):
    is_policy_acknowledged = forms.BooleanField(
        label=(
            "I read and agree to the requirements for registering "
            "and operating .gov domains."
        )
    )
