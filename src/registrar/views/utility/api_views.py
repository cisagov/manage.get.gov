import logging
from django.http import JsonResponse
from django.forms.models import model_to_dict
from registrar.models import FederalAgency, SeniorOfficial
from django.utils.dateformat import format
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.db.models import Q

logger = logging.getLogger(__name__)


@login_required
def get_senior_official_from_federal_agency_json(request):
    """Returns federal_agency information as a JSON"""

    # This API is only accessible to admins
    superuser_perm = request.user.has_perm("registrar.full_access_permission")
    analyst_perm = request.user.has_perm("registrar.analyst_access_permission")
    if not request.user.is_authenticated or not analyst_perm or not superuser_perm:
        # We intentionally don't return anything here
        return {}

    agency_name = request.GET.get("agency_name")
    agency = FederalAgency.objects.filter(agency=agency_name).first()
    senior_official = SeniorOfficial.objects.filter(federal_agency=agency).first()
    if agency and senior_official:
        # Convert the agency object to a dictionary
        so_dict = model_to_dict(senior_official)
        return JsonResponse(so_dict)
    else:
        return JsonResponse({"error": "Senior Official not found"})