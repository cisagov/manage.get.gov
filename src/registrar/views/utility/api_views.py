import logging
from django.http import JsonResponse
from django.forms.models import model_to_dict
from registrar.decorators import IS_CISA_ANALYST, IS_FULL_ACCESS, IS_OMB_ANALYST, IS_PORTFOLIO_MEMBER, grant_access
from registrar.models import FederalAgency, SeniorOfficial, DomainRequest
from registrar.utility.admin_helpers import get_action_needed_reason_default_email, get_rejection_reason_default_email
from registrar.models.portfolio import Portfolio
from registrar.utility.constants import BranchChoices
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse

logger = logging.getLogger(__name__)


@grant_access(IS_CISA_ANALYST, IS_OMB_ANALYST, IS_FULL_ACCESS)
def get_senior_official_from_federal_agency_json(request):
    """Returns federal_agency information as a JSON"""

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


@grant_access(IS_CISA_ANALYST, IS_OMB_ANALYST, IS_FULL_ACCESS)
def get_portfolio_json(request):
    """Returns portfolio information as a JSON"""

    portfolio_id = request.GET.get("id")
    try:
        portfolio = Portfolio.objects.get(id=portfolio_id)
    except Portfolio.DoesNotExist:
        return JsonResponse({"error": "Portfolio not found"}, status=404)

    # Convert the portfolio to a dictionary
    portfolio_dict = model_to_dict(portfolio)

    portfolio_dict["id"] = portfolio.id

    # map portfolio federal type
    portfolio_dict["federal_type"] = (
        BranchChoices.get_branch_label(portfolio.federal_type) if portfolio.federal_type else "-"
    )

    # map portfolio organization type
    portfolio_dict["organization_type"] = (
        DomainRequest.OrganizationChoices.get_org_label(portfolio.organization_type)
        if portfolio.organization_type
        else "-"
    )

    # Add senior official information if it exists
    if portfolio.senior_official:
        senior_official = model_to_dict(
            portfolio.senior_official, fields=["id", "first_name", "last_name", "title", "phone", "email"]
        )
        # The phone number field isn't json serializable, so we
        # convert this to a string first if it exists.
        if "phone" in senior_official and senior_official.get("phone"):
            senior_official["phone"] = str(senior_official["phone"])
        portfolio_dict["senior_official"] = senior_official
    else:
        portfolio_dict["senior_official"] = None

    # Add federal agency information if it exists
    if portfolio.federal_agency:
        federal_agency = model_to_dict(portfolio.federal_agency, fields=["agency", "id"])
        portfolio_dict["federal_agency"] = federal_agency
    else:
        portfolio_dict["federal_agency"] = "-"

    return JsonResponse(portfolio_dict)


@grant_access(IS_CISA_ANALYST, IS_OMB_ANALYST, IS_FULL_ACCESS)
def get_suborganization_list_json(request):
    """Returns suborganization list information for a portfolio as a JSON"""

    portfolio_id = request.GET.get("portfolio_id")
    try:
        portfolio = Portfolio.objects.get(id=portfolio_id)
    except Portfolio.DoesNotExist:
        return JsonResponse({"error": "Portfolio not found"}, status=404)

    # Add suborganizations related to this portfolio
    suborganizations = portfolio.portfolio_suborganizations.all().values("id", "name")
    results = [{"id": sub["id"], "text": sub["name"]} for sub in suborganizations]
    return JsonResponse({"results": results, "pagination": {"more": False}})


@grant_access(IS_CISA_ANALYST, IS_OMB_ANALYST, IS_FULL_ACCESS)
def get_federal_and_portfolio_types_from_federal_agency_json(request):
    """Returns specific portfolio information as a JSON. Request must have
    both agency_name and organization_type."""

    federal_type = None
    portfolio_type = None

    agency_name = request.GET.get("agency_name")
    agency = FederalAgency.objects.filter(agency=agency_name).first()
    if agency:
        federal_type = Portfolio.get_federal_type(agency)
        federal_type = BranchChoices.get_branch_label(federal_type) if federal_type else "-"

    response_data = {
        "portfolio_type": portfolio_type,
        "federal_type": federal_type,
    }

    return JsonResponse(response_data)


@grant_access(IS_CISA_ANALYST, IS_OMB_ANALYST, IS_FULL_ACCESS)
def get_action_needed_email_for_user_json(request):
    """Returns a default action needed email for a given user"""

    reason = request.GET.get("reason")
    domain_request_id = request.GET.get("domain_request_id")
    if not reason:
        return JsonResponse({"error": "No reason specified"}, status=404)

    if not domain_request_id:
        return JsonResponse({"error": "No domain_request_id specified"}, status=404)

    domain_request = DomainRequest.objects.filter(id=domain_request_id).first()

    email = get_action_needed_reason_default_email(domain_request, reason)
    return JsonResponse({"email": email}, status=200)


@grant_access(IS_CISA_ANALYST, IS_OMB_ANALYST, IS_FULL_ACCESS)
def get_rejection_email_for_user_json(request):
    """Returns a default rejection email for a given user"""

    reason = request.GET.get("reason")
    domain_request_id = request.GET.get("domain_request_id")
    if not reason:
        return JsonResponse({"error": "No reason specified"}, status=404)

    if not domain_request_id:
        return JsonResponse({"error": "No domain_request_id specified"}, status=404)

    domain_request = DomainRequest.objects.filter(id=domain_request_id).first()
    email = get_rejection_reason_default_email(domain_request, reason)
    return JsonResponse({"email": email}, status=200)

@grant_access(IS_PORTFOLIO_MEMBER, IS_FULL_ACCESS)
def set_portfolio_in_session(request, portfolio_pk):
    """
    Handles updating active portfolio in session.
    """
    portfolio = get_object_or_404(Portfolio, pk=portfolio_pk)
    request.session["portfolio"] = portfolio

    logger.info("Successfully set active portfolio to ", portfolio)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": success_message}, status=200)
    return redirect(reverse("domains"))