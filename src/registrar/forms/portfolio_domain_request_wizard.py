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

class RequestingEntity(RegistrarForm):
    is_policy_acknowledged = forms.BooleanField(
        label="I read and agree to the requirements for operating a .gov domain.",
        error_messages={
            "required": ("Check the box if you read and agree to the requirements for operating a .gov domain.")
        },
    )
