from django.http import JsonResponse
from django.core.paginator import Paginator
from registrar.models import UserDomainRole, Domain
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.db.models import Q
import logging
logger = logging.getLogger(__name__)


@login_required
def get_domains_json(request):
    """Given the current request,
    get all domains that are associated with the UserDomainRole object"""

    user_domain_roles = UserDomainRole.objects.filter(user=request.user)
    domain_ids = user_domain_roles.values_list("domain_id", flat=True)

    objects = Domain.objects.filter(id__in=domain_ids)
    unfiltered_total = objects.count()

    # Handle sorting
    sort_by = request.GET.get("sort_by", "id")  # Default to 'id'
    order = request.GET.get("order", "asc")  # Default to 'asc'

    # Handle search term
    search_term = request.GET.get("search_term")
    if search_term:
        objects = objects.filter(Q(name__icontains=search_term))

    # Handle state
    status_param = request.GET.get("status")
    if status_param:
        status_list = status_param.split(",")

        # if unknown is in status_list, append 'dns needed'
        if 'unknown' in status_list:
            status_list.append('dns needed')

        logger.debug(f"Submitted status_list: {status_list}")

        # Split the status list into normal states and custom states
        normal_states = [state for state in status_list if state in Domain.State.values]
        custom_states = [state for state in status_list if state == "expired"]

        # Construct Q objects for normal states that can be queried through ORM
        state_query = Q()
        if normal_states:
            state_query |= Q(state__in=normal_states)

        # Handle custom states in Python, as expired can not be queried through ORM
        if "expired" in custom_states:
            expired_domain_ids = [domain.id for domain in objects if domain.state_display() == "Expired"]
            state_query |= Q(id__in=expired_domain_ids)

        logger.debug(f"State query: {state_query}")

        # Apply the combined query
        objects = objects.filter(state_query)

        # If there are filtered states, and expired is not one of them, domains with
        # state_display of 'Expired' must be removed
        if "expired" not in custom_states:
            expired_domain_ids = [domain.id for domain in objects if domain.state_display() == "Expired"]
            objects = objects.exclude(id__in=expired_domain_ids)

    if sort_by == "state_display":
        # Fetch the objects and sort them in Python
        objects = list(objects)  # Evaluate queryset to a list
        objects.sort(key=lambda domain: domain.state_display(), reverse=(order == "desc"))
    else:
        if order == "desc":
            sort_by = f"-{sort_by}"
        objects = objects.order_by(sort_by)

    paginator = Paginator(objects, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Convert objects to JSON-serializable format
    domains = [
        {
            "id": domain.id,
            "name": domain.name,
            "expiration_date": domain.expiration_date,
            "state": domain.state,
            "state_display": domain.state_display(),
            "get_state_help_text": domain.get_state_help_text(),
            "action_url": reverse("domain", kwargs={"pk": domain.id}),
            "action_label": ("View" if domain.state in [Domain.State.DELETED, Domain.State.ON_HOLD] else "Manage"),
            "svg_icon": ("visibility" if domain.state in [Domain.State.DELETED, Domain.State.ON_HOLD] else "settings"),
        }
        for domain in page_obj.object_list
    ]

    return JsonResponse(
        {
            "domains": domains,
            "page": page_obj.number,
            "num_pages": paginator.num_pages,
            "has_previous": page_obj.has_previous(),
            "has_next": page_obj.has_next(),
            "total": paginator.count,
            "unfiltered_total": unfiltered_total,
        }
    )
