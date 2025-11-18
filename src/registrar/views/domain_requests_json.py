from django.apps import apps
from django.http import JsonResponse
from django.core.paginator import Paginator
from registrar.decorators import grant_access, ALL
from registrar.models import DomainRequest
from django.utils.dateformat import format
from django.urls import reverse
from django.db.models import Q


@grant_access(ALL)
def get_domain_requests_json(request):
    """Given the current request,
    get all domain requests that are associated with the request user and exclude the APPROVED ones.
    If we are on the portfolio requests page, limit the response to only those requests associated with
    the given portfolio."""

    domain_request_ids = _get_domain_request_ids_from_request(request)

    objects = DomainRequest.objects.filter(id__in=domain_request_ids)
    unfiltered_total = objects.count()

    objects = _apply_search(objects, request)
    objects = _apply_status_filter(objects, request)
    objects = _apply_sorting(objects, request)

    paginator = Paginator(objects, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)
    domain_requests = [
        _serialize_domain_request(request, domain_request, request.user) for domain_request in page_obj.object_list
    ]

    return JsonResponse(
        {
            "domain_requests": domain_requests,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
            "page": page_obj.number,
            "num_pages": paginator.num_pages,
            "total": paginator.count,
            "unfiltered_total": unfiltered_total,
        }
    )


def _get_domain_request_ids_from_request(request):
    """Get domain request ids from request.

    If portfolio specified, return domain request ids associated with portfolio.
    Otherwise, return domain request ids associated with request.user.

    If ?portfolio=<id> is provided:
    - verify user can view that portfolio
    - if user has VIEW_ALL_REQUESTS all in portfolio
    - else only user's own in portfolio
    Else:
    - only user's own requests
    Excludes APPROVED always.
    """
    qs = DomainRequest.objects.exclude(status=DomainRequest.DomainRequestStatus.APPROVED)
    portfolio_id = request.GET.get("portfolio")

    if not portfolio_id:
        return qs.filter(requester=request.user).values_list("id", flat=True)

    Portfolio = apps.get_model("registrar", "Portfolio")
    portfolio = Portfolio.objects.filter(pk=portfolio_id).first()
    if not portfolio or not request.user.has_view_portfolio_permission(portfolio):
        return qs.none().values_list("id", flat=True)

    if request.user.has_view_all_requests_portfolio_permission(portfolio):
        return qs.filter(portfolio=portfolio_id).values_list("id", flat=True)

    return qs.filter(portfolio=portfolio_id, requester=request.user).values_list("id", flat=True)


def _apply_search(queryset, request):
    search_term = request.GET.get("search_term")
    is_portfolio = request.GET.get("portfolio")

    if search_term:
        search_term_lower = search_term.lower()
        new_domain_request_text = "new domain request"

        # Check if the search term is a substring of 'New domain request'
        # If yes, we should return domain requests that do not have a
        # requested_domain (those display as New domain request in the UI)
        if search_term_lower in new_domain_request_text:
            queryset = queryset.filter(
                Q(requested_domain__name__icontains=search_term) | Q(requested_domain__isnull=True)
            )
        elif is_portfolio:
            queryset = queryset.filter(
                Q(requested_domain__name__icontains=search_term)
                | Q(requester__first_name__icontains=search_term)
                | Q(requester__last_name__icontains=search_term)
                | Q(requester__email__icontains=search_term)
            )
        # For non org users
        else:
            queryset = queryset.filter(Q(requested_domain__name__icontains=search_term))
    return queryset


def _apply_status_filter(queryset, request):
    status_param = request.GET.get("status")
    if status_param:
        status_list = status_param.split(",")
        statuses = [status for status in status_list if status in DomainRequest.DomainRequestStatus.values]
        # Construct Q objects for statuses that can be queried through ORM
        status_query = Q()
        if statuses:
            status_query |= Q(status__in=statuses)
        # Apply the combined query
        queryset = queryset.filter(status_query)

    return queryset


def _apply_sorting(queryset, request):
    sort_by = request.GET.get("sort_by", "id")  # Default to 'id'
    order = request.GET.get("order", "asc")  # Default to 'asc'

    # Handle special case for 'requester'
    if sort_by == "requester":
        sort_by = "requester__email"

    if order == "desc":
        sort_by = f"-{sort_by}"
    return queryset.order_by(sort_by)


def _serialize_domain_request(request, domain_request, user):

    deletable_statuses = [
        DomainRequest.DomainRequestStatus.STARTED,
        DomainRequest.DomainRequestStatus.WITHDRAWN,
    ]

    # Determine action label based on user permissions and request status
    editable_statuses = [
        DomainRequest.DomainRequestStatus.STARTED,
        DomainRequest.DomainRequestStatus.ACTION_NEEDED,
        DomainRequest.DomainRequestStatus.WITHDRAWN,
    ]

    # Statuses that should only allow viewing (not managing)
    view_only_statuses = [
        DomainRequest.DomainRequestStatus.REJECTED,
    ]

    # No portfolio action_label
    if domain_request.requester == user:
        if domain_request.status in editable_statuses:
            action_label = "Edit"
        elif domain_request.status in view_only_statuses:
            action_label = "View"
        else:
            action_label = "Manage"
    else:
        action_label = "View"

    # No portfolio deletable
    is_deletable = domain_request.status in deletable_statuses

    # If we're working with a portfolio
    portfolio_id = request.GET.get("portfolio")
    portfolio = None
    if portfolio_id:
        Portfolio = apps.get_model("registrar", "Portfolio")
        portfolio = Portfolio.objects.filter(pk=portfolio_id).first()
    if portfolio_id and user.is_org_user_for_portfolio(portfolio_id):
        is_deletable = (
            domain_request.status in deletable_statuses and user.has_edit_request_portfolio_permission(portfolio)
        ) and domain_request.requester == user
        if user.has_edit_request_portfolio_permission(portfolio) and domain_request.requester == user:
            if domain_request.status in editable_statuses:
                action_label = "Edit"
            elif domain_request.status in view_only_statuses:
                action_label = "View"
            else:
                action_label = "Manage"
        else:
            action_label = "View"

    # Map the action label to corresponding URLs and icons
    action_url_map = {
        "Edit": reverse("edit-domain-request", kwargs={"domain_request_pk": domain_request.id}),
        "Manage": reverse("domain-request-status", kwargs={"domain_request_pk": domain_request.id}),
        "View": reverse("domain-request-status-viewonly", kwargs={"domain_request_pk": domain_request.id}),
    }

    svg_icon_map = {"Edit": "edit", "Manage": "settings", "View": "visibility"}

    return {
        "requested_domain": domain_request.requested_domain.name if domain_request.requested_domain else None,
        "last_submitted_date": domain_request.last_submitted_date,
        "status": domain_request.get_status_display(),
        "created_at": format(domain_request.created_at, "c"),  # Serialize to ISO 8601
        "requester": domain_request.requester.email,
        "id": domain_request.id,
        "is_deletable": is_deletable,
        "action_url": action_url_map.get(action_label),
        "action_label": action_label,
        "svg_icon": svg_icon_map.get(action_label),
    }
