from __future__ import annotations
from typing import Union
from .domain_application import DomainApplication

import logging

from django.apps import apps
from django.db import models


logger = logging.getLogger(__name__)

class DomainInformation(DomainApplication):
    security_email = models.EmailField(
        max_length=320,
        null=True,
        blank=True,
        help_text="Security email for public use",
    )
 