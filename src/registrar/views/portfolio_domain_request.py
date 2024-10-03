import logging
from collections import defaultdict
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import resolve, reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from django.contrib import messages
from registrar.forms import portfolio_domain_request_wizard as forms
from registrar.forms.utility.wizard_form_helper import request_step_list
from registrar.models import DomainRequest
from registrar.models.contact import Contact
from registrar.models.user import User
from registrar.views.domain_request import DomainRequestWizard
from registrar.views.utility import StepsHelper
from registrar.views.utility.permission_views import DomainRequestPermissionDeleteView
from registrar.utility.enums import Step, PortfolioDomainRequestStep

from .utility import (
    DomainRequestPermissionView,
    DomainRequestPermissionWithdrawView,
    DomainRequestWizardPermissionView,
    DomainRequestPortfolioViewonlyView,
)

logger = logging.getLogger(__name__)


# TODO - this is a WIP until the domain request experience for portfolios is complete
class PortfolioDomainRequestWizard(DomainRequestWizard):
    StepEnum: PortfolioDomainRequestStep = PortfolioDomainRequestStep  # type: ignore
    URL_NAMESPACE = "portfolio-domain-request"
    EDIT_URL_NAME = "edit-portfolio-domain-request"
    NEW_URL_NAME = "/portfolio/request/"
    TITLES = {
        StepEnum.REQUESTING_ENTITY: _("Requesting entity"),
        StepEnum.CURRENT_SITES: _("Current websites"),
        StepEnum.DOTGOV_DOMAIN: _(".gov domain"),
        StepEnum.PURPOSE: _("Purpose of your domain"),
        StepEnum.ADDITIONAL_DETAILS: _("Additional details"),
        StepEnum.REQUIREMENTS: _("Requirements for operating a .gov domain"),
        StepEnum.REVIEW: _("Review and submit your domain request"),
    }

    WIZARD_CONDITIONS = {}

    def __init__(self):
        super().__init__()
        self.steps = StepsHelper(self)
        self._domain_request = None  # for caching
    
    def redirect_to_intro_or_first_step(self, request):
        # if accessing this class directly, redirect to either to an acknowledgement
        # page or to the first step in the processes (if an edit rather than a new request);
        # subclasseswill NOT be redirected. The purpose of this is to allow code to
        # send users "to the domain request wizard" without needing to know which view
        # is first in the list of steps.
        if self.__class__ == PortfolioDomainRequestWizard:
            if request.path_info == self.NEW_URL_NAME:
                # Clear context so the prop getter won't create a request here.
                # Creating a request will be handled in the post method for the
                # intro page.
                return render(request, "domain_request_intro.html", {})
            else:
                return self.goto(self.steps.first)
        return None


# Portfolio pages
class RequestingEntity(PortfolioDomainRequestWizard):
    template_name = "portfolio_domain_request_requesting_entity.html"
    forms = [forms.RequestingEntity]
