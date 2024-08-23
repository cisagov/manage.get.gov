import logging
from django.http import JsonResponse
from django.forms.models import model_to_dict
from registrar.models import FederalAgency, SeniorOfficial
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required

from registrar.models.portfolio import Portfolio
from registrar.utility.constants import BranchChoices

logger = logging.getLogger(__name__)


@login_required
@staff_member_required
def get_senior_official_from_federal_agency_json(request):
    """Returns federal_agency information as a JSON"""

    # This API is only accessible to admins and analysts
    superuser_perm = request.user.has_perm("registrar.full_access_permission")
    analyst_perm = request.user.has_perm("registrar.analyst_access_permission")
    if not request.user.is_authenticated or not any([analyst_perm, superuser_perm]):
        return JsonResponse({"error": "You do not have access to this resource"}, status=403)

    agency_name = request.GET.get("agency_name")
    agency = FederalAgency.objects.filter(agency=agency_name).first()
    senior_official = SeniorOfficial.objects.filter(federal_agency=agency).first()
    if agency and senior_official:
        # Convert the agency object to a dictionary
        so_dict = model_to_dict(senior_official)

        # The phone number field isn't json serializable, so we
        # convert this to a string first if it exists.
        if "phone" in so_dict and so_dict.get("phone"):
            so_dict["phone"] = str(so_dict["phone"])

        return JsonResponse(so_dict)
    else:
        return JsonResponse({"error": "Senior Official not found"}, status=404)


@login_required
@staff_member_required
def get_federal_and_portfolio_types_from_federal_agency_json(request):
    """Returns specific portfolio information as a JSON. Request must have
    both agency_name and organization_type."""

    # This API is only accessible to admins and analysts
    superuser_perm = request.user.has_perm("registrar.full_access_permission")
    analyst_perm = request.user.has_perm("registrar.analyst_access_permission")
    if not request.user.is_authenticated or not any([analyst_perm, superuser_perm]):
        return JsonResponse({"error": "You do not have access to this resource"}, status=403)

    federal_type = None
    portfolio_type = None

    agency_name = request.GET.get("agency_name")
    organization_type = request.GET.get("organization_type")
    agency = FederalAgency.objects.filter(agency=agency_name).first()
    if agency:
        federal_type = Portfolio.get_federal_type(agency)
        portfolio_type = Portfolio.get_portfolio_type(organization_type, federal_type)
        federal_type = BranchChoices.get_branch_label(federal_type) if federal_type else "-"

    response_data = {
        "portfolio_type": portfolio_type,
        "federal_type": federal_type,
    }

    return JsonResponse(response_data)
