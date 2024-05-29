from django.http import JsonResponse
from django.core.paginator import Paginator
from registrar.models import DomainRequest


def get_domain_requests_json(request):
    """Given the current request,
    get all domain requests that are associated with the request user and exclude the APPROVED ones"""

    if not request.user.is_authenticated:
        return JsonResponse({"error": "User not authenticated"}, status=401)

    domain_requests = DomainRequest.objects.filter(creator=request.user).exclude(
        status=DomainRequest.DomainRequestStatus.APPROVED
    )
    # Handle sorting
    sort_by = request.GET.get("sort_by", "id")  # Default to 'id'
    order = request.GET.get("order", "asc")  # Default to 'asc'
    if order == "desc":
        sort_by = f"-{sort_by}"
    domain_requests = domain_requests.order_by(sort_by)
    page_number = request.GET.get("page", 1)
    paginator = Paginator(domain_requests, 10)
    page_obj = paginator.get_page(page_number)

    domain_requests_data = [
        {
            "requested_domain": domain_request.requested_domain.name if domain_request.requested_domain else None,
            "submission_date": domain_request.submission_date,
            "status": domain_request.get_status_display(),
            "created_at": domain_request.created_at,
            "id": domain_request.id,
            "is_deletable": domain_request.status
            in [DomainRequest.DomainRequestStatus.STARTED, DomainRequest.DomainRequestStatus.WITHDRAWN],
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
        }
    )
