"""Containers helpers and base classes for the domain_request_wizard.py file"""

from itertools import zip_longest
from typing import Callable
from django.db.models.fields.related import ForeignObjectRel
from django import forms
from registrar.models import DomainRequest, Contact


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

        if isinstance(obj, DomainRequest):
            obj.save(optimistic_lock=True)
        else:
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
        obj.save(optimistic_lock=True)

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
        obj.save(optimistic_lock=True)


class BaseYesNoForm(RegistrarForm):
    """
    Base class used for forms with a yes/no form with a hidden input on toggle.
    Use this class when you need something similar to the AdditionalDetailsYesNoForm.

    Attributes:
        form_is_checked (bool): Determines the default state (checked or not) of the Yes/No toggle.
        field_name (str): Specifies the form field name that the Yes/No toggle controls.
        required_error_message (str): Custom error message displayed when the field is required but not provided.
        form_choices (tuple): Defines the choice options for the form field, defaulting to Yes/No choices.

    Usage:
        Subclass this form to implement specific Yes/No fields in various parts of the application, customizing
        `form_is_checked` and `field_name` as necessary for the context.
    """

    form_is_checked: bool

    # What field does the yes/no button hook to?
    # For instance, this could be "has_other_contacts"
    field_name: str

    # This field can be overriden to show a custom error
    # message.
    required_error_message = "This question is required."

    # We need to add aria_labels in the backend for this particular
    # widget instead of the frontend.  While for most other inputs
    # you could normally utilize {% with ..} statements, but for
    # the TypedChoiceField this will not populate the aria_labels.
    # This is because TypedChoiceField doesn't expose attributes
    # as readily as other widgets (we are also utilizing RadioSelect
    # with it, so it further complicates the DOM).
    aria_label = ""
    aria_labelledby = ""

    # Default form choice mapping. Default is suitable for most cases.
    # Override for more complex scenarios.
    form_choices = ((True, "Yes"), (False, "No"))

    def __init__(self, *args, **kwargs):
        """Extend the initialization of the form from RegistrarForm __init__"""
        super().__init__(*args, **kwargs)

        self.fields[self.field_name] = self.get_typed_choice_field()

    def get_typed_choice_field(self):
        """
        Creates a TypedChoiceField for the form with specified initial value and choices.
        Returns:
            TypedChoiceField: A Django form field specifically configured for selecting between
            predefined choices with type coercion and custom error messages.
        """
        choice_field = forms.TypedChoiceField(
            coerce=lambda x: x.lower() == "true" if x is not None else None,
            choices=self.form_choices,
            initial=self.get_initial_value(),
            widget=forms.RadioSelect(attrs={"aria-label": self.aria_label, "aria-labelledby": self.aria_labelledby}),
            error_messages={
                "required": self.required_error_message,
            },
        )

        return choice_field

    def get_initial_value(self):
        """
        Determines the initial value for TypedChoiceField.
        More directly, this controls the "initial" field on forms.TypedChoiceField.

        Returns:
            bool | None: The initial value for the form field. If the domain request is set,
            this will always return the value of self.form_is_checked.
            Otherwise, None will be returned as a new domain request can't start out checked.
        """
        # No pre-selection for new domain requests
        initial_value = self.form_is_checked if self.domain_request else None
        return initial_value


def request_step_list(request_wizard, step_enum):
    """Dynamically generated list of steps in the form wizard."""
    step_list = []
    for step in step_enum:
        condition = request_wizard.wizard_conditions.get(step, True)
        if callable(condition):
            condition = condition(request_wizard)
        if condition:
            step_list.append(step)
    return step_list
