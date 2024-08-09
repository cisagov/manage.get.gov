from __future__ import annotations  # allows forward references in annotations
import logging
from api.views import DOMAIN_API_MESSAGES
from phonenumber_field.formfields import PhoneNumberField  # type: ignore

from django import forms
from django.core.validators import RegexValidator, MaxLengthValidator
from django.utils.safestring import mark_safe

from registrar.forms.utility.wizard_form_helper import (
    RegistrarForm,
    RegistrarFormSet,
    BaseYesNoForm,
    BaseDeletableRegistrarForm,
)
from registrar.models import Contact, DomainRequest, DraftDomain, Domain, FederalAgency
from registrar.templatetags.url_helpers import public_site_url
from registrar.utility.enums import ValidationReturnType
from registrar.utility.constants import BranchChoices

logger = logging.getLogger(__name__)


class OrganizationTypeForm(RegistrarForm):
    generic_org_type = forms.ChoiceField(
        # use the long names in the domain request form
        choices=DomainRequest.OrganizationChoicesVerbose.choices,
        widget=forms.RadioSelect,
        error_messages={"required": "Select the type of organization you represent."},
    )


class TribalGovernmentForm(RegistrarForm):
    federally_recognized_tribe = forms.BooleanField(
        label="Federally-recognized tribe ",
        required=False,
    )

    state_recognized_tribe = forms.BooleanField(
        label="State-recognized tribe ",
        required=False,
    )

    tribe_name = forms.CharField(
        label="Name of tribe",
        error_messages={"required": "Enter the tribe you represent."},
    )

    def clean(self):
        """Needs to be either state or federally recognized."""
        if not (self.cleaned_data["federally_recognized_tribe"] or self.cleaned_data["state_recognized_tribe"]):
            raise forms.ValidationError(
                # no sec because we are using it to include an internal URL
                # into a link. There should be no user-facing input in the
                # HTML indicated here.
                mark_safe(  # nosec
                    "You can’t complete this domain request yet. "
                    "Only tribes recognized by the U.S. federal government "
                    "or by a U.S. state government are eligible for .gov "
                    'domains. Use our <a href="{}">contact form</a> to '
                    "tell us more about your tribe and why you want a .gov "
                    "domain. We’ll review your information and get back "
                    "to you.".format(public_site_url("contact"))
                ),
                code="invalid",
            )


class OrganizationFederalForm(RegistrarForm):
    federal_type = forms.ChoiceField(
        choices=BranchChoices.choices,
        widget=forms.RadioSelect,
        error_messages={"required": ("Select the part of the federal government your organization is in.")},
    )


class OrganizationElectionForm(RegistrarForm):
    is_election_board = forms.NullBooleanField(
        widget=forms.RadioSelect(
            choices=[
                (True, "Yes"),
                (False, "No"),
            ],
        )
    )

    def clean_is_election_board(self):
        """This box must be checked to proceed but offer a clear error."""
        # already converted to a boolean
        is_election_board = self.cleaned_data["is_election_board"]
        if is_election_board is None:
            raise forms.ValidationError(
                ("Select “Yes” if you represent an election office. Select “No” if you don’t."),
                code="required",
            )
        return is_election_board


class OrganizationContactForm(RegistrarForm):
    # for federal agencies we also want to know the top-level agency.
    excluded_agencies = ["gov Administration", "Non-Federal Agency"]
    federal_agency = forms.ModelChoiceField(
        label="Federal agency",
        # not required because this field won't be filled out unless
        # it is a federal agency. Use clean to check programatically
        # if it has been filled in when required.
        # uncomment to see if modelChoiceField can be an arg later
        required=False,
        queryset=FederalAgency.objects.exclude(agency__in=excluded_agencies),
        empty_label="--Select--",
    )
    organization_name = forms.CharField(
        label="Organization name",
        error_messages={"required": "Enter the name of your organization."},
    )
    address_line1 = forms.CharField(
        label="Street address",
        error_messages={"required": "Enter the street address of your organization."},
    )
    address_line2 = forms.CharField(
        required=False,
        label="Street address line 2 (optional)",
    )
    city = forms.CharField(
        label="City",
        error_messages={"required": "Enter the city where your organization is located."},
    )
    state_territory = forms.ChoiceField(
        label="State, territory, or military post",
        choices=[("", "--Select--")] + DomainRequest.StateTerritoryChoices.choices,
        error_messages={
            "required": ("Select the state, territory, or military post where your organization is located.")
        },
    )
    zipcode = forms.CharField(
        label="Zip code",
        validators=[
            RegexValidator(
                "^[0-9]{5}(?:-[0-9]{4})?$|^$",
                message="Enter a zip code in the form of 12345 or 12345-6789.",
            )
        ],
        error_messages={"required": ("Enter a zip code in the form of 12345 or 12345-6789.")},
    )
    urbanization = forms.CharField(
        required=False,
        label="Urbanization (required for Puerto Rico only)",
    )

    def clean_federal_agency(self):
        """Require something to be selected when this is a federal agency."""
        federal_agency = self.cleaned_data.get("federal_agency", None)
        # need the domain request object to know if this is federal
        if self.domain_request is None:
            # hmm, no saved domain request object?, default require the agency
            if not federal_agency:
                # no answer was selected
                raise forms.ValidationError(
                    "Select the federal agency your organization is in.",
                    code="required",
                )
        if self.domain_request.is_federal():
            if not federal_agency:
                # no answer was selected
                raise forms.ValidationError(
                    "Select the federal agency your organization is in.",
                    code="required",
                )
        return federal_agency


class AboutYourOrganizationForm(RegistrarForm):
    about_your_organization = forms.CharField(
        label="About your organization",
        widget=forms.Textarea(),
        validators=[
            MaxLengthValidator(
                2000,
                message="Response must be less than 2000 characters.",
            )
        ],
        error_messages={"required": ("Enter more information about your organization.")},
    )


class SeniorOfficialForm(RegistrarForm):
    JOIN = "senior_official"

    def to_database(self, obj):
        if not self.is_valid():
            return
        contact = getattr(obj, "senior_official", None)
        if contact is not None and not contact.has_more_than_one_join("senior_official"):
            # if contact exists in the database and is not joined to other entities
            super().to_database(contact)
        else:
            # no contact exists OR contact exists which is joined also to other entities;
            # in either case, create a new contact and update it
            contact = Contact()
            super().to_database(contact)
            obj.senior_official = contact
            obj.save()

    @classmethod
    def from_database(cls, obj):
        contact = getattr(obj, "senior_official", None)
        return super().from_database(contact)

    first_name = forms.CharField(
        label="First name / given name",
        error_messages={"required": ("Enter the first name / given name of your senior official.")},
    )
    last_name = forms.CharField(
        label="Last name / family name",
        error_messages={"required": ("Enter the last name / family name of your senior official.")},
    )
    title = forms.CharField(
        label="Title or role in your organization",
        error_messages={
            "required": (
                "Enter the title or role your senior official has in your"
                " organization (e.g., Chief Information Officer)."
            )
        },
    )
    email = forms.EmailField(
        label="Email",
        max_length=None,
        error_messages={"invalid": ("Enter an email address in the required format, like name@example.com.")},
        validators=[
            MaxLengthValidator(
                320,
                message="Response must be less than 320 characters.",
            )
        ],
    )


class CurrentSitesForm(RegistrarForm):
    website = forms.URLField(
        required=False,
        label="Public website",
        error_messages={
            "invalid": ("Enter your organization's current website in the required format, like example.com.")
        },
    )


class BaseCurrentSitesFormSet(RegistrarFormSet):
    JOIN = "current_websites"

    def should_delete(self, cleaned):
        website = cleaned.get("website", "")
        return website.strip() == ""

    def to_database(self, obj: DomainRequest):
        # If we want to test against multiple joins for a website object, replace the empty array
        # and change the JOIN in the models to allow for reverse references
        self._to_database(obj, self.JOIN, self.should_delete, self.pre_update, self.pre_create)

    @classmethod
    def from_database(cls, obj):
        return super().from_database(obj, cls.JOIN, cls.on_fetch)


CurrentSitesFormSet = forms.formset_factory(
    CurrentSitesForm,
    extra=1,
    absolute_max=1500,  # django default; use `max_num` to limit entries
    formset=BaseCurrentSitesFormSet,
)


class AlternativeDomainForm(RegistrarForm):
    def clean_alternative_domain(self):
        """Validation code for domain names."""
        requested = self.cleaned_data.get("alternative_domain", None)
        validated, _ = DraftDomain.validate_and_handle_errors(
            domain=requested,
            return_type=ValidationReturnType.FORM_VALIDATION_ERROR,
            blank_ok=True,
        )
        return validated

    alternative_domain = forms.CharField(
        required=False,
        label="Alternative domain",
    )


class BaseAlternativeDomainFormSet(RegistrarFormSet):
    JOIN = "alternative_domains"

    def should_delete(self, cleaned):
        domain = cleaned.get("alternative_domain", "")
        return domain.strip() == ""

    def pre_update(self, db_obj, cleaned):
        domain = cleaned.get("alternative_domain", None)
        if domain is not None:
            db_obj.website = f"{domain}.gov"

    def pre_create(self, db_obj, cleaned):
        domain = cleaned.get("alternative_domain", None)
        if domain is not None:
            return {"website": f"{domain}.gov"}
        else:
            return {}

    def to_database(self, obj: DomainRequest):
        # If we want to test against multiple joins for a website object, replace the empty array and
        # change the JOIN in the models to allow for reverse references
        self._to_database(obj, self.JOIN, self.should_delete, self.pre_update, self.pre_create)

    @classmethod
    def on_fetch(cls, query):
        return [{"alternative_domain": Domain.sld(domain.website)} for domain in query]

    @classmethod
    def from_database(cls, obj):
        return super().from_database(obj, cls.JOIN, cls.on_fetch)


AlternativeDomainFormSet = forms.formset_factory(
    AlternativeDomainForm,
    extra=1,
    absolute_max=1500,  # django default; use `max_num` to limit entries
    formset=BaseAlternativeDomainFormSet,
)


class DotGovDomainForm(RegistrarForm):
    def to_database(self, obj):
        if not self.is_valid():
            return
        domain = self.cleaned_data.get("requested_domain", None)
        if domain:
            requested_domain = getattr(obj, "requested_domain", None)
            if requested_domain is not None:
                requested_domain.name = f"{domain}.gov"
                requested_domain.save()
            else:
                requested_domain = DraftDomain.objects.create(name=f"{domain}.gov")
                obj.requested_domain = requested_domain
                obj.save()

        obj.save()

    @classmethod
    def from_database(cls, obj):
        values = {}
        requested_domain = getattr(obj, "requested_domain", None)
        if requested_domain is not None:
            domain_name = requested_domain.name
            values["requested_domain"] = Domain.sld(domain_name)
        return values

    def clean_requested_domain(self):
        """Validation code for domain names."""
        requested = self.cleaned_data.get("requested_domain", None)
        validated, _ = DraftDomain.validate_and_handle_errors(
            domain=requested,
            return_type=ValidationReturnType.FORM_VALIDATION_ERROR,
        )
        return validated

    requested_domain = forms.CharField(
        label="What .gov domain do you want?",
        error_messages={
            "required": DOMAIN_API_MESSAGES["required"],
        },
    )


class PurposeForm(RegistrarForm):
    purpose = forms.CharField(
        label="Purpose",
        widget=forms.Textarea(),
        validators=[
            MaxLengthValidator(
                2000,
                message="Response must be less than 2000 characters.",
            )
        ],
        error_messages={"required": "Describe how you’ll use the .gov domain you’re requesting."},
    )


class YourContactForm(RegistrarForm):
    JOIN = "submitter"

    def to_database(self, obj):
        if not self.is_valid():
            return
        contact = getattr(obj, "submitter", None)
        if contact is not None and not contact.has_more_than_one_join("submitted_domain_requests"):
            # if contact exists in the database and is not joined to other entities
            super().to_database(contact)
        else:
            # no contact exists OR contact exists which is joined also to other entities;
            # in either case, create a new contact and update it
            contact = Contact()
            super().to_database(contact)
            obj.submitter = contact
            obj.save()

    @classmethod
    def from_database(cls, obj):
        contact = getattr(obj, "submitter", None)
        return super().from_database(contact)

    first_name = forms.CharField(
        label="First name / given name",
        error_messages={"required": "Enter your first name / given name."},
    )
    middle_name = forms.CharField(
        required=False,
        label="Middle name (optional)",
    )
    last_name = forms.CharField(
        label="Last name / family name",
        error_messages={"required": "Enter your last name / family name."},
    )
    title = forms.CharField(
        label="Title or role in your organization",
        error_messages={
            "required": ("Enter your title or role in your organization (e.g., Chief Information Officer).")
        },
    )
    email = forms.EmailField(
        label="Email",
        max_length=None,
        error_messages={"invalid": ("Enter your email address in the required format, like name@example.com.")},
        validators=[
            MaxLengthValidator(
                320,
                message="Response must be less than 320 characters.",
            )
        ],
    )
    phone = PhoneNumberField(
        label="Phone",
        error_messages={"invalid": "Enter a valid 10-digit phone number.", "required": "Enter your phone number."},
    )


class OtherContactsYesNoForm(BaseYesNoForm):
    """The yes/no field for the OtherContacts form."""

    form_choices = ((True, "Yes, I can name other employees."), (False, "No. (We’ll ask you to explain why.)"))
    field_name = "has_other_contacts"

    @property
    def form_is_checked(self):
        """
        Determines the initial checked state of the form based on the domain_request's attributes.
        """
        if self.domain_request.has_other_contacts():
            return True
        elif self.domain_request.has_rationale():
            return False
        else:
            # No pre-selection for new domain requests
            return None


class OtherContactsForm(RegistrarForm):
    first_name = forms.CharField(
        label="First name / given name",
        error_messages={"required": "Enter the first name / given name of this contact."},
    )
    middle_name = forms.CharField(
        required=False,
        label="Middle name (optional)",
    )
    last_name = forms.CharField(
        label="Last name / family name",
        error_messages={"required": "Enter the last name / family name of this contact."},
    )
    title = forms.CharField(
        label="Title or role in your organization",
        error_messages={
            "required": (
                "Enter the title or role in your organization of this contact (e.g., Chief Information Officer)."
            )
        },
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
    )
    phone = PhoneNumberField(
        label="Phone",
        error_messages={
            "invalid": "Enter a valid 10-digit phone number.",
            "required": "Enter a phone number for this contact.",
        },
    )

    def __init__(self, *args, **kwargs):
        """
        Override the __init__ method for RegistrarForm.
        Set form_data_marked_for_deletion to false.
        Empty_permitted set to False, as this is overridden in certain circumstances by
        Django's BaseFormSet, and results in empty forms being allowed and field level
        errors not appropriately raised. This works with code in the view which appropriately
        displays required attributes on fields.
        """
        self.form_data_marked_for_deletion = False
        super().__init__(*args, **kwargs)
        self.empty_permitted = False

    def mark_form_for_deletion(self):
        self.form_data_marked_for_deletion = True

    def clean(self):
        """
        This method overrides the default behavior for forms.
        This cleans the form after field validation has already taken place.
        In this override, allow for a form which is deleted by user or marked for
        deletion by formset to be considered valid even though certain required fields have
        not passed field validation
        """
        if self.form_data_marked_for_deletion or self.cleaned_data.get("DELETE"):
            # clear any errors raised by the form fields
            # (before this clean() method is run, each field
            # performs its own clean, which could result in
            # errors that we wish to ignore at this point)
            #
            # NOTE: we cannot just clear() the errors list.
            # That causes problems.
            for field in self.fields:
                if field in self.errors:
                    del self.errors[field]
            # return empty object with only 'delete' attribute defined.
            # this will prevent _to_database from creating an empty
            # database object
            return {"DELETE": True}

        return self.cleaned_data


class BaseOtherContactsFormSet(RegistrarFormSet):
    """
    FormSet for Other Contacts

    There are two conditions by which a form in the formset can be marked for deletion.
    One is if the user clicks 'DELETE' button, and this is submitted in the form. The
    other is if the YesNo form, which is submitted with this formset, is set to No; in
    this case, all forms in formset are marked for deletion. Both of these conditions
    must co-exist.
    Also, other_contacts have db relationships to multiple db objects. When attempting
    to delete an other_contact from a domain request, those db relationships must be
    tested and handled.
    """

    JOIN = "other_contacts"

    def get_deletion_widget(self):
        return forms.HiddenInput(attrs={"class": "deletion"})

    def __init__(self, *args, **kwargs):
        """
        Override __init__ for RegistrarFormSet.
        """
        self.formset_data_marked_for_deletion = False
        self.domain_request = kwargs.pop("domain_request", None)
        super(RegistrarFormSet, self).__init__(*args, **kwargs)
        # quick workaround to ensure that the HTML `required`
        # attribute shows up on required fields for the first form
        # in the formset plus those that have data already.
        for index in range(max(self.initial_form_count(), 1)):
            self.forms[index].use_required_attribute = True

    def should_delete(self, cleaned):
        """
        Implements should_delete method from BaseFormSet.
        """
        return self.formset_data_marked_for_deletion or cleaned.get("DELETE", False)

    def pre_create(self, db_obj, cleaned):
        """Code to run before an item in the formset is created in the database."""
        # remove DELETE from cleaned
        if "DELETE" in cleaned:
            cleaned.pop("DELETE")
        return cleaned

    def to_database(self, obj: DomainRequest):
        self._to_database(obj, self.JOIN, self.should_delete, self.pre_update, self.pre_create)

    @classmethod
    def from_database(cls, obj):
        return super().from_database(obj, cls.JOIN, cls.on_fetch)

    def mark_formset_for_deletion(self):
        """Mark other contacts formset for deletion.
        Updates forms in formset as well to mark them for deletion.
        This has an effect on validity checks and to_database methods.
        """
        self.formset_data_marked_for_deletion = True
        for form in self.forms:
            form.mark_form_for_deletion()

    def is_valid(self):
        """Extend is_valid from RegistrarFormSet. When marking this formset for deletion, set
        validate_min to false so that validation does not attempt to enforce a minimum
        number of other contacts when contacts marked for deletion"""
        if self.formset_data_marked_for_deletion:
            self.validate_min = False
        return super().is_valid()


OtherContactsFormSet = forms.formset_factory(
    OtherContactsForm,
    extra=0,
    absolute_max=1500,  # django default; use `max_num` to limit entries
    min_num=1,
    can_delete=True,
    validate_min=True,
    formset=BaseOtherContactsFormSet,
)


class NoOtherContactsForm(BaseDeletableRegistrarForm):
    no_other_contacts_rationale = forms.CharField(
        required=True,
        # label has to end in a space to get the label_suffix to show
        label=("No other employees rationale"),
        widget=forms.Textarea(),
        validators=[
            MaxLengthValidator(
                1000,
                message="Response must be less than 1000 characters.",
            )
        ],
        error_messages={"required": ("Rationale for no other employees is required.")},
    )


class CisaRepresentativeForm(BaseDeletableRegistrarForm):
    cisa_representative_first_name = forms.CharField(
        label="First name / given name",
        error_messages={"required": "Enter the first name / given name of the CISA regional representative."},
    )
    cisa_representative_last_name = forms.CharField(
        label="Last name / family name",
        error_messages={"required": "Enter the last name / family name of the CISA regional representative."},
    )
    cisa_representative_email = forms.EmailField(
        label="Your representative’s email (optional)",
        max_length=None,
        required=False,
        error_messages={
            "invalid": ("Enter your representative’s email address in the required format, like name@example.com."),
        },
        validators=[
            MaxLengthValidator(
                320,
                message="Response must be less than 320 characters.",
            )
        ],
    )


class CisaRepresentativeYesNoForm(BaseYesNoForm):
    """Yes/no toggle for the CISA regions question on additional details"""

    form_is_checked = property(lambda self: self.domain_request.has_cisa_representative)  # type: ignore
    field_name = "has_cisa_representative"


class AnythingElseForm(BaseDeletableRegistrarForm):
    anything_else = forms.CharField(
        required=True,
        label="Anything else?",
        widget=forms.Textarea(),
        validators=[
            MaxLengthValidator(
                2000,
                message="Response must be less than 2000 characters.",
            )
        ],
        error_messages={
            "required": (
                "Provide additional details you’d like us to know. " "If you have nothing to add, select “No.”"
            )
        },
    )


class AnythingElseYesNoForm(BaseYesNoForm):
    """Yes/no toggle for the anything else question on additional details"""

    # Note that these can be set as functions/init if you need more fine-grained control.
    form_is_checked = property(lambda self: self.domain_request.has_anything_else_text)  # type: ignore
    field_name = "has_anything_else_text"


class RequirementsForm(RegistrarForm):
    is_policy_acknowledged = forms.BooleanField(
        label="I read and agree to the requirements for operating a .gov domain.",
        error_messages={
            "required": ("Check the box if you read and agree to the requirements for operating a .gov domain.")
        },
    )
