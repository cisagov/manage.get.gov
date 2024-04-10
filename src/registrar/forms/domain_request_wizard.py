from __future__ import annotations  # allows forward references in annotations
from itertools import zip_longest
import logging
from typing import Callable
from api.views import DOMAIN_API_MESSAGES
from phonenumber_field.formfields import PhoneNumberField  # type: ignore

from django import forms
from django.core.validators import RegexValidator, MaxLengthValidator
from django.utils.safestring import mark_safe
from django.db.models.fields.related import ForeignObjectRel

from registrar.models import Contact, DomainRequest, DraftDomain, Domain
from registrar.templatetags.url_helpers import public_site_url
from registrar.utility.enums import ValidationReturnType

logger = logging.getLogger(__name__)


class RegistrarForm(forms.Form):
    """
    A common set of methods and configuration.

    The registrar's domain request is several pages of "steps".
    Each step is an HTML form containing one or more Django "forms".

    Subclass this class to create new forms.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        # save a reference to a domain request object
        self.domain_request = kwargs.pop("domain_request", None)
        super(RegistrarForm, self).__init__(*args, **kwargs)

    def to_database(self, obj: DomainRequest | Contact):
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
    def from_database(cls, obj: DomainRequest | Contact | None):
        """Returns a dict of form field values gotten from `obj`."""
        if obj is None:
            return {}
        return {name: getattr(obj, name) for name in cls.declared_fields.keys()}  # type: ignore


class RegistrarFormSet(forms.BaseFormSet):
    """
    As with RegistrarForm, a common set of methods and configuration.

    Subclass this class to create new formsets.
    """

    def __init__(self, *args, **kwargs):
        # save a reference to an domain_request object
        self.domain_request = kwargs.pop("domain_request", None)
        super(RegistrarFormSet, self).__init__(*args, **kwargs)
        # quick workaround to ensure that the HTML `required`
        # attribute shows up on required fields for any forms
        # in the formset which have data already (stated another
        # way: you can leave a form in the formset blank, but
        # if you opt to fill it out, you must fill it out _right_)
        for index in range(self.initial_form_count()):
            self.forms[index].use_required_attribute = True

    def should_delete(self, cleaned):
        """Should this entry be deleted from the database?"""
        raise NotImplementedError

    def pre_update(self, db_obj, cleaned):
        """Code to run before an item in the formset is saved."""
        for key, value in cleaned.items():
            setattr(db_obj, key, value)

    def pre_create(self, db_obj, cleaned):
        """Code to run before an item in the formset is created in the database."""
        return cleaned

    def to_database(self, obj: DomainRequest):
        """
        Adds this form's cleaned data to `obj` and saves `obj`.

        Does nothing if form is not valid.

        Hint: Subclass should call `self._to_database(...)`.
        """
        raise NotImplementedError

    def _to_database(
        self,
        obj: DomainRequest,
        join: str,
        should_delete: Callable,
        pre_update: Callable,
        pre_create: Callable,
    ):
        """
        Performs the actual work of saving.

        Has hooks such as `should_delete` and `pre_update` by which the
        subclass can control behavior. Add more hooks whenever needed.
        """
        if not self.is_valid():
            return
        obj.save()

        query = getattr(obj, join).order_by("created_at").all()  # order matters

        # get the related name for the join defined for the db_obj for this form.
        # the related name will be the reference on a related object back to db_obj
        related_name = ""
        field = obj._meta.get_field(join)
        if isinstance(field, ForeignObjectRel) and callable(field.related_query_name):
            related_name = field.related_query_name()
        elif hasattr(field, "related_query_name") and callable(field.related_query_name):
            related_name = field.related_query_name()

        # the use of `zip` pairs the forms in the formset with the
        # related objects gotten from the database -- there should always be
        # at least as many forms as database entries: extra forms means new
        # entries, but fewer forms is _not_ the correct way to delete items
        # (likely a client-side error or an attempt at data tampering)
        for db_obj, post_data in zip_longest(query, self.forms, fillvalue=None):
            cleaned = post_data.cleaned_data if post_data is not None else {}

            # matching database object exists, update it
            if db_obj is not None and cleaned:
                if should_delete(cleaned):
                    if hasattr(db_obj, "has_more_than_one_join") and db_obj.has_more_than_one_join(related_name):
                        # Remove the specific relationship without deleting the object
                        getattr(db_obj, related_name).remove(self.domain_request)
                    else:
                        # If there are no other relationships, delete the object
                        db_obj.delete()
                else:
                    if hasattr(db_obj, "has_more_than_one_join") and db_obj.has_more_than_one_join(related_name):
                        # create a new db_obj and disconnect existing one
                        getattr(db_obj, related_name).remove(self.domain_request)
                        kwargs = pre_create(db_obj, cleaned)
                        getattr(obj, join).create(**kwargs)
                    else:
                        pre_update(db_obj, cleaned)
                        db_obj.save()

            # no matching database object, create it
            # make sure not to create a database object if cleaned has 'delete' attribute
            elif db_obj is None and cleaned and not cleaned.get("DELETE", False):
                kwargs = pre_create(db_obj, cleaned)
                getattr(obj, join).create(**kwargs)

    @classmethod
    def on_fetch(cls, query):
        """Code to run when fetching formset's objects from the database."""
        return query.values()

    @classmethod
    def from_database(cls, obj: DomainRequest, join: str, on_fetch: Callable):
        """Returns a dict of form field values gotten from `obj`."""
        return on_fetch(getattr(obj, join).order_by("created_at"))  # order matters


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
        choices=DomainRequest.BranchChoices.choices,
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
    federal_agency = forms.ChoiceField(
        label="Federal agency",
        # not required because this field won't be filled out unless
        # it is a federal agency. Use clean to check programatically
        # if it has been filled in when required.
        required=False,
        choices=[("", "--Select--")] + DomainRequest.AGENCY_CHOICES,
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


class AuthorizingOfficialForm(RegistrarForm):
    JOIN = "authorizing_official"

    def to_database(self, obj):
        if not self.is_valid():
            return
        contact = getattr(obj, "authorizing_official", None)
        if contact is not None and not contact.has_more_than_one_join("authorizing_official"):
            # if contact exists in the database and is not joined to other entities
            super().to_database(contact)
        else:
            # no contact exists OR contact exists which is joined also to other entities;
            # in either case, create a new contact and update it
            contact = Contact()
            super().to_database(contact)
            obj.authorizing_official = contact
            obj.save()

    @classmethod
    def from_database(cls, obj):
        contact = getattr(obj, "authorizing_official", None)
        return super().from_database(contact)

    first_name = forms.CharField(
        label="First name / given name",
        error_messages={"required": ("Enter the first name / given name of your authorizing official.")},
    )
    last_name = forms.CharField(
        label="Last name / family name",
        error_messages={"required": ("Enter the last name / family name of your authorizing official.")},
    )
    title = forms.CharField(
        label="Title or role in your organization",
        error_messages={
            "required": (
                "Enter the title or role your authorizing official has in your"
                " organization (e.g., Chief Information Officer)."
            )
        },
    )
    email = forms.EmailField(
        label="Email",
        error_messages={"invalid": ("Enter an email address in the required format, like name@example.com.")},
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
        error_messages={"invalid": ("Enter your email address in the required format, like name@example.com.")},
    )
    phone = PhoneNumberField(
        label="Phone",
        error_messages={"invalid": "Enter a valid 10-digit phone number.", "required": "Enter your phone number."},
    )


class OtherContactsYesNoForm(RegistrarForm):
    def __init__(self, *args, **kwargs):
        """Extend the initialization of the form from RegistrarForm __init__"""
        super().__init__(*args, **kwargs)
        # set the initial value based on attributes of domain request
        if self.domain_request and self.domain_request.has_other_contacts():
            initial_value = True
        elif self.domain_request and self.domain_request.has_rationale():
            initial_value = False
        else:
            # No pre-selection for new domain requests
            initial_value = None

        self.fields["has_other_contacts"] = forms.TypedChoiceField(
            coerce=lambda x: x.lower() == "true" if x is not None else None,  # coerce strings to bool, excepting None
            choices=((True, "Yes, I can name other employees."), (False, "No. (We’ll ask you to explain why.)")),
            initial=initial_value,
            widget=forms.RadioSelect,
            error_messages={
                "required": "This question is required.",
            },
        )


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
        error_messages={
            "required": ("Enter an email address in the required format, like name@example.com."),
            "invalid": ("Enter an email address in the required format, like name@example.com."),
        },
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

class BaseDeletableRegistrarForm(RegistrarForm):
    """Adds special validation and delete functionality.
    Used by forms that are tied to a Yes/No form."""
    def __init__(self, *args, **kwargs):
        self.form_data_marked_for_deletion = False
        super().__init__(*args, **kwargs)

    def mark_form_for_deletion(self):
        """Marks this form for deletion.
        This changes behavior of validity checks and to_database
        methods."""
        self.form_data_marked_for_deletion = True

    def clean(self):
        """
        This method overrides the default behavior for forms.
        This cleans the form after field validation has already taken place.
        In this override, remove errors associated with the form if form data
        is marked for deletion.
        """

        if self.form_data_marked_for_deletion:
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

        return self.cleaned_data

    def to_database(self, obj):
        """
        This method overrides the behavior of RegistrarForm.
        If form data is marked for deletion, set relevant fields
        to None before saving.
        Do nothing if form is not valid.
        """
        if not self.is_valid():
            return
        if self.form_data_marked_for_deletion:
            for field_name, _ in self.fields.items():
                setattr(obj, field_name, None)
        else:
            for name, value in self.cleaned_data.items():
                setattr(obj, name, value)
        obj.save()

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
    cisa_representative_email = forms.EmailField(
        required=False,
        label="Are you working with a CISA representative?", #TODO-NL: (design check) - is this the right label?
    )

class CisaRepresentativeYesNoForm(RegistrarForm):
    def __init__(self, *args, **kwargs):
        """Extend the initialization of the form from RegistrarForm __init__"""
        super().__init__(*args, **kwargs)
        # set the initial value based on attributes of domain request
        if self.domain_request:
            if self.domain_request.has_cisa_representative():
                initial_value = True
            else:
                initial_value = False
        else:
            # No pre-selection for new domain requests
            initial_value = None

        self.fields["has_cisa_representative"] = forms.TypedChoiceField(
            coerce=lambda x: x.lower() == "true" if x is not None else None,  # coerce strings to bool, excepting None
            choices=((True, "Yes"), (False, "No")),
            initial=initial_value,
            widget=forms.RadioSelect,
            error_messages={
                "required": "This question is required.", 
            },
        )


class AdditionalDetailsForm(BaseDeletableRegistrarForm):
    anything_else = forms.CharField(
        required=False,
        label="Anything else?",
        widget=forms.Textarea(),
        validators=[
            MaxLengthValidator(
                2000,
                message="Response must be less than 2000 characters.",
            )
        ],
    )

class AdditionalDetailsYesNoForm(RegistrarForm):
    def __init__(self, *args, **kwargs):
        """Extend the initialization of the form from RegistrarForm __init__"""
        super().__init__(*args, **kwargs)
        # set the initial value based on attributes of domain request
        if self.domain_request:
            if self.domain_request.has_anything_else_text():
                initial_value = True
            else:
                initial_value = False
        else:
            # No pre-selection for new domain requests
            initial_value = None

        self.fields["has_anything_else_text"] = forms.TypedChoiceField(
            coerce=lambda x: x.lower() == "true" if x is not None else None,  # coerce strings to bool, excepting None
            choices=((True, "Yes"), (False, "No")),
            initial=initial_value,
            widget=forms.RadioSelect,
            error_messages={
                "required": "This question is required.", #TODO-NL: (design check) - is this required?
            },
        )

class RequirementsForm(RegistrarForm):
    is_policy_acknowledged = forms.BooleanField(
        label="I read and agree to the requirements for operating a .gov domain.",
        error_messages={
            "required": ("Check the box if you read and agree to the requirements for operating a .gov domain.")
        },
    )
