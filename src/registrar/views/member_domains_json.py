import logging
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.views import View
from registrar.models import UserDomainRole, Domain, DomainInformation, User
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.db.models import Q

from registrar.models.domain_invitation import DomainInvitation
from registrar.views.utility.mixins import PortfolioMemberDomainsPermission

logger = logging.getLogger(__name__)


class PortfolioMemberDomainsJson(PortfolioMemberDomainsPermission, View):

    def get(self, request):
        """Given the current request,
        get all domains that are associated with the portfolio, or
        associated with the member/invited member"""

        domain_ids = self.get_domain_ids_from_request(request)

        objects = Domain.objects.filter(id__in=domain_ids).select_related("domain_info__sub_organization")
        unfiltered_total = objects.count()

        objects = self.apply_search(objects, request)
        objects = self.apply_state_filter(objects, request)
        objects = self.apply_sorting(objects, request)

        paginator = Paginator(objects, 10)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        domains = [self.serialize_domain(domain, request.user) for domain in page_obj.object_list]

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


    def get_domain_ids_from_request(self, request):
        """Get domain ids from request.

        request.get.email - email address of invited member
        request.get.member - member id of member
        request.get.portfolio - portfolio id of portfolio
        request.get.member_only - whether to return only domains associated with member
        or to return all domains in the portfolio
        """
        portfolio = request.GET.get("portfolio")
        email = request.GET.get("email")
        member_id = request.GET.get("member")
        member_only = request.GET.get("member_only", "false").lower() in ["true", "1"]
        if member_only:
            if member_id:
                member = get_object_or_404(User, pk=member_id)
                domain_info_ids = DomainInformation.objects.filter(portfolio=portfolio).values_list("domain_id", flat=True)
                user_domain_roles = UserDomainRole.objects.filter(user=member).values_list("domain_id", flat=True)
                return domain_info_ids.intersection(user_domain_roles)
            elif email:
                domain_info_ids = DomainInformation.objects.filter(portfolio=portfolio).values_list("domain_id", flat=True)
                domain_invitations = DomainInvitation.objects.filter(email=email).values_list("domain_id", flat=True)
                return domain_info_ids.intersection(domain_invitations)
        else:
            domain_infos = DomainInformation.objects.filter(portfolio=portfolio)
            return domain_infos.values_list("domain_id", flat=True)
        logger.warning("Invalid search criteria, returning empty results list")         
        return []


    def apply_search(self, queryset, request):
        search_term = request.GET.get("search_term")
        if search_term:
            queryset = queryset.filter(Q(name__icontains=search_term))
        return queryset


    def apply_state_filter(self, queryset, request):
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
            custom_states = [state for state in status_list if state == "expired"]
            # Construct Q objects for normal states that can be queried through ORM
            state_query = Q()
            if normal_states:
                state_query |= Q(state__in=normal_states)
            # Handle custom states in Python, as expired can not be queried through ORM
            if "expired" in custom_states:
                expired_domain_ids = [domain.id for domain in queryset if domain.state_display() == "Expired"]
                state_query |= Q(id__in=expired_domain_ids)
            # Apply the combined query
            queryset = queryset.filter(state_query)
            # If there are filtered states, and expired is not one of them, domains with
            # state_display of 'Expired' must be removed
            if "expired" not in custom_states:
                expired_domain_ids = [domain.id for domain in queryset if domain.state_display() == "Expired"]
                queryset = queryset.exclude(id__in=expired_domain_ids)

        return queryset


    def apply_sorting(self, queryset, request):
        sort_by = request.GET.get("sort_by", "id")
        order = request.GET.get("order", "asc")
        if sort_by == "state_display":
            objects = list(queryset)
            objects.sort(key=lambda domain: domain.state_display(), reverse=(order == "desc"))
            return objects
        else:
            if order == "desc":
                sort_by = f"-{sort_by}"
            return queryset.order_by(sort_by)


    def serialize_domain(self, domain, user):
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
            "state_display": domain.state_display(),
            "get_state_help_text": domain.get_state_help_text(),
            "action_url": reverse("domain", kwargs={"pk": domain.id}),
            "action_label": ("View" if view_only else "Manage"),
            "svg_icon": ("visibility" if view_only else "settings"),
            "domain_info__sub_organization": suborganization_name,
        }
