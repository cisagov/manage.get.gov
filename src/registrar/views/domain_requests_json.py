from django.http import JsonResponse
from django.core.paginator import Paginator
from registrar.models import DomainRequest
from django.utils.dateformat import format
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.db.models import Q


@login_required
def get_domain_requests_json(request):
    """Given the current request,
    get all domain requests that are associated with the request user and exclude the APPROVED ones"""

    domain_requests = DomainRequest.objects.filter(creator=request.user).exclude(
        status=DomainRequest.DomainRequestStatus.APPROVED
    )
    unfiltered_total = domain_requests.count()

    # Handle sorting
    sort_by = request.GET.get("sort_by", "id")  # Default to 'id'
    order = request.GET.get("order", "asc")  # Default to 'asc'
    search_term = request.GET.get("search_term")

    if search_term:
        search_term_lower = search_term.lower()
        new_domain_request_text = "new domain request"

        # Check if the search term is a substring of 'New domain request'
        # If yes, we should return domain requests that do not have a
        # requested_domain (those display as New domain request in the UI)
        if search_term_lower in new_domain_request_text:
            domain_requests = domain_requests.filter(
                Q(requested_domain__name__icontains=search_term) | Q(requested_domain__isnull=True)
            )
        else:
            domain_requests = domain_requests.filter(Q(requested_domain__name__icontains=search_term))

    if order == "desc":
        sort_by = f"-{sort_by}"
    domain_requests = domain_requests.order_by(sort_by)
    page_number = request.GET.get("page", 1)
    paginator = Paginator(domain_requests, 10)
    page_obj = paginator.get_page(page_number)

    domain_requests_data = [
        {
            "requested_domain": domain_request.requested_domain.name if domain_request.requested_domain else None,
            "last_submitted_date": domain_request.last_submitted_date,
            "status": domain_request.get_status_display(),
            "created_at": format(domain_request.created_at, "c"),  # Serialize to ISO 8601
            "id": domain_request.id,
            "is_deletable": domain_request.status
            in [DomainRequest.DomainRequestStatus.STARTED, DomainRequest.DomainRequestStatus.WITHDRAWN],
            "action_url": (
                reverse("edit-domain-request", kwargs={"id": domain_request.id})
                if domain_request.status
                in [
                    DomainRequest.DomainRequestStatus.STARTED,
                    DomainRequest.DomainRequestStatus.ACTION_NEEDED,
                    DomainRequest.DomainRequestStatus.WITHDRAWN,
                ]
                else reverse("domain-request-status", kwargs={"pk": domain_request.id})
            ),
            "action_label": (
                "Edit"
                if domain_request.status
                in [
                    DomainRequest.DomainRequestStatus.STARTED,
                    DomainRequest.DomainRequestStatus.ACTION_NEEDED,
                    DomainRequest.DomainRequestStatus.WITHDRAWN,
                ]
                else "Manage"
            ),
            "svg_icon": (
                "edit"
                if domain_request.status
                in [
                    DomainRequest.DomainRequestStatus.STARTED,
                    DomainRequest.DomainRequestStatus.ACTION_NEEDED,
                    DomainRequest.DomainRequestStatus.WITHDRAWN,
                ]
                else "settings"
            ),
        }
        for domain_request in page_obj
    ]

    return JsonResponse(
        {
            "domain_requests": domain_requests_data,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
            "page": page_obj.number,
            "num_pages": paginator.num_pages,
            "total": paginator.count,
            "unfiltered_total": unfiltered_total,
        }
    )
