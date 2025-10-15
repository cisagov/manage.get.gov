from django.apps import apps
from django.core.checks import register, Warning, Tags, Info
from django.db import models

from django.core.validators import MaxLengthValidator
from django import forms
import importlib
import inspect


MODELS_TAG = "dotgov_models"
FORMS_TAG = "dotgov_forms"

# These lists exclude matching elements from being checked
EXCLUDE_MODULE_PREFIXES = {
    "django.contrib",  # Probably don't need to be concerned with Django forms
    "debug_toolbar",  # Probably don't need to be concerned with debug toolbar
    "import_export",  # Probably don't need to be concerned with import_export
}
EXCLUDE_CLASS_SUFFIXES = {
    "BaseYesNoForm",  # Dynamic form, can't process at this time
    "RequestingEntityForm",  # Dynamic form, can't process at this time
    "RequestingEntityYesNoForm",  # Dynamic form, can't process at this time
}
EXCLUDE_FIELD_NAMES = {
    # TBD
}


@register(Tags.models, MODELS_TAG)
def validate_textfield_maxlength(app_configs, **kwargs):
    issues = []
    for model in apps.get_models():
        # Check model for CharFields without maxlength
        issues.extend(_validate_charfields_maxlength(model))

    return issues


def _validate_charfields_maxlength(model):
    issues = []
    for field in model._meta.get_fields():
        if isinstance(field, models.CharField):
            maxlen_method = getattr(field, "max_length", None)
            if maxlen_method is None:
                issues.append(
                    Warning(
                        f"Model {model.__name__}.{field.name} is a CharField without max_length",
                        hint="Set max_length on CharField",
                        obj=field,
                        id="DOTGOV.W001",
                    )
                )
    return issues


@register(Tags.models, FORMS_TAG)
def validate_forms_maxlength(app_configs, **kwargs):
    # Each module will report a single multi-line issue as a CheckMessage dictating any problem(s) found, collected here
    issues = []
    for app_config in apps.get_app_configs():
        # print(f"Checking app_config: {app_config}")
        modname = f"{app_config.name}.forms"
        if _module_excluded(modname):
            continue
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue

        # Record header info for appconfig
        header_appconfig = f"{app_config.label}"
        for cname, cls in inspect.getmembers(mod, inspect.isclass):
            if not issubclass(cls, forms.BaseForm) or cls in (forms.BaseForm, forms.Form):
                continue

            if _class_excluded(cls):
                continue
            try:
                form = cls()
            except Exception:
                print(f"Exception encountered, Skipping forms module: {modname}.{cls.__name__}")
                continue

            # Record header info for class
            header_classname = f"{cls.__name__}"
            # Failures will be stored here as a list of strings
            lines = []
            lines.extend(_validate_form_fields(form))

            # Check for one or more failures in previous class scan
            if len(lines) > 0:
                # Create a message block by joining all the lines
                block = "\n".join(lines)
                block = header_appconfig + "\n" + header_classname + "\n" + block

                # Now that the failed checks have been joined, create a single CheckMessage for that module
                issues.append(
                    Warning(
                        block,
                        hint="Add max_length= or a MaxLengthValidator to these fields.\n",
                        obj=f"{modname}",
                        id="DOTGOV.W002",
                    )
                )
                lines = []  # reset for next class

    return issues


def _validate_form_fields(form):
    lines = []
    # Scan each field in the form class
    for fname, f in form.fields.items():
        if _field_excluded(fname):
            continue
        if isinstance(f, forms.CharField):
            has_max = getattr(f, "max_length", None) is not None
            has_validator = any(isinstance(v, MaxLengthValidator) for v in getattr(f, "validators", []))
            if not (has_max or has_validator):
                # store the failure information as a string
                lines.append(f"\t{fname} is a CharField without max_length")
    return lines


def _module_excluded(modname: str) -> bool:
    return any(modname.startswith(pfx) for pfx in EXCLUDE_MODULE_PREFIXES)


def _class_excluded(cls) -> bool:
    return any(cls.__name__.endswith(sfx) for sfx in EXCLUDE_CLASS_SUFFIXES)


def _field_excluded(field_name: str) -> bool:
    return field_name in EXCLUDE_FIELD_NAMES
