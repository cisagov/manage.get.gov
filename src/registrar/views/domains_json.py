import logging
from django.apps import apps
from django.http import JsonResponse
from django.core.paginator import Paginator
from registrar.decorators import grant_access, ALL
from registrar.models import UserDomainRole, Domain, DomainInformation
from django.urls import reverse
from django.db.models import Q
from waffle import flag_is_active

logger = logging.getLogger(__name__)


@grant_access(ALL)
def get_domains_json(request):
    """Given the current request,
    get all domains that are associated with the UserDomainRole object"""

    domain_ids = get_domain_ids_from_request(request)

    objects = Domain.objects.filter(id__in=domain_ids).select_related("domain_info__sub_organization")
    unfiltered_total = objects.count()

    objects = apply_search(objects, request)
    objects = apply_state_filter(objects, request)
    objects = apply_sorting(objects, request)

    paginator = Paginator(objects, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    domains = [serialize_domain(domain, request) for domain in page_obj.object_list]

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


def get_domain_ids_from_request(request):
    """Get domain ids from request.

    If portfolio specified, return domain ids associated with portfolio.
    - require has_view_portfolio_permission(portfolio_obj)
    - if has_view_all_domains_portfolio_permission(portfolio_obj): return all portfolio domains
    - else: return only portfolio domains the user manages
    Else: return the domains the user manages (legacy path).
    """
    user = request.user
    portfolio_param = request.GET.get("portfolio")

    if portfolio_param:
        # resolve to object
        try:
            pid = int(portfolio_param)
        except (TypeError, ValueError):
            return Domain.objects.none().values_list("id", flat=True)

        Portfolio = apps.get_model("registrar", "Portfolio")
        portfolio = Portfolio.objects.filter(pk=pid).first()
        if not portfolio:
            return Domain.objects.none().values_list("id", flat=True)

        # must be able to view portfolio
        if not user.has_view_portfolio_permission(portfolio):
            return Domain.objects.none().values_list("id", flat=True)

        # all domains in portfolio
        if user.has_view_all_domains_portfolio_permission(portfolio):
            return DomainInformation.objects.filter(portfolio=portfolio).values_list("domain_id", flat=True)

        # only domains this user manages within this portfolio
        return (
            DomainInformation.objects.filter(portfolio=portfolio, domain__permissions__user=user)
            .values_list("domain_id", flat=True)
            .distinct()
        )

    # No portfolio param = legacy/non-org path: only domains the user manages
    qs = UserDomainRole.objects.filter(user=user)

    # Further adjust query result when the multiple_portfolios flag is on
    if flag_is_active(request, "multiple_portfolios"):
        # Detect if this user manages any portfolio domains at all
        managed_domain_ids = qs.values_list("domain_id", flat=True)
        has_portfolio_domains = DomainInformation.objects.filter(
            domain_id__in=managed_domain_ids,
            portfolio__isnull=False,
        ).exists()

        if has_portfolio_domains:
            # In the mixed case (user has portfolio + legacy domains),
            # the legacy view should show only legacy-only domains
            qs = qs.filter(
                Q(domain__domain_info__isnull=True) |
                Q(domain__domain_info__portfolio__isnull=True)
            )

    return qs.values_list("domain_id", flat=True).distinct()

def apply_search(queryset, request):
    search_term = request.GET.get("search_term")
    if search_term:
        queryset = queryset.filter(Q(name__icontains=search_term))
    return queryset


def apply_state_filter(queryset, request):
    status_param = request.GET.get("status")
    if status_param:
        status_list = status_param.split(",")
        # if unknown is in status_list, append 'dns needed' since both
        # unknown and dns needed display as DNS Needed, and both are
        # searchable via state parameter of 'unknown'
        if "unknown" in status_list:
            status_list.append("dns needed")
        # Split the status list into normal states and custom states
        normal_states = [state for state in status_list if state in Domain.State.values]
        custom_states = [state for state in status_list if (state == "expired" or state == "expiring")]
        # Construct Q objects for normal states that can be queried through ORM
        state_query = Q()
        if normal_states:
            state_query |= Q(state__in=normal_states)
        # Handle custom states in Python, as expired can not be queried through ORM
        if "expired" in custom_states:
            expired_domain_ids = [domain.id for domain in queryset if domain.state_display(request) == "Expired"]
            state_query |= Q(id__in=expired_domain_ids)
        if "expiring" in custom_states:
            expiring_domain_ids = [domain.id for domain in queryset if domain.state_display(request) == "Expiring soon"]
            state_query |= Q(id__in=expiring_domain_ids)
        # Apply the combined query
        queryset = queryset.filter(state_query)
        # If there are filtered states, and expired is not one of them, domains with
        # state_display of 'Expired' must be removed
        if "expired" not in custom_states:
            expired_domain_ids = [domain.id for domain in queryset if domain.state_display(request) == "Expired"]
            queryset = queryset.exclude(id__in=expired_domain_ids)
        if "expiring" not in custom_states:
            expired_domain_ids = [domain.id for domain in queryset if domain.state_display(request) == "Expiring soon"]
            queryset = queryset.exclude(id__in=expired_domain_ids)

    return queryset


def apply_sorting(queryset, request):
    sort_by = request.GET.get("sort_by", "id")
    order = request.GET.get("order", "asc")
    if sort_by == "state_display":
        objects = list(queryset)
        objects.sort(key=lambda domain: domain.state_display(request), reverse=(order == "desc"))
        return objects
    else:
        if order == "desc":
            sort_by = f"-{sort_by}"
        return queryset.order_by(sort_by)


def serialize_domain(domain, request):
    user = request.user
    suborganization_name = None
    try:
        domain_info = domain.domain_info
        if domain_info:
            suborganization = domain_info.sub_organization
            if suborganization:
                suborganization_name = suborganization.name
    except Domain.domain_info.RelatedObjectDoesNotExist:
        domain_info = None
        logger.debug(f"Issue in domains_json: We could not find domain_info for {domain}")

    # Check if there is a UserDomainRole for this domain and user
    user_domain_role_exists = UserDomainRole.objects.filter(domain_id=domain.id, user=user).exists()
    view_only = not user_domain_role_exists or domain.state in [Domain.State.DELETED, Domain.State.ON_HOLD]
    return {
        "id": domain.id,
        "name": domain.name,
        "expiration_date": domain.expiration_date,
        "state": domain.state,
        "state_display": domain.state_display(request),
        "get_state_help_text": domain.get_state_help_text(),
        "action_url": reverse("domain", kwargs={"domain_pk": domain.id}),
        "action_label": ("View" if view_only else "Manage"),
        "svg_icon": ("visibility" if view_only else "settings"),
        "domain_info__sub_organization": suborganization_name,
    }
