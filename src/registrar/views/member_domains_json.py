import logging
from django.db import models
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.views import View
from registrar.decorators import HAS_PORTFOLIO_MEMBERS_ANY_PERM, grant_access
from registrar.models import UserDomainRole, Domain, DomainInformation, User
from django.urls import reverse
from django.db.models import Q

from registrar.models.domain_invitation import DomainInvitation

logger = logging.getLogger(__name__)


@grant_access(HAS_PORTFOLIO_MEMBERS_ANY_PERM)
class PortfolioMemberDomainsJson(View):

    def get(self, request):
        """Given the current request,
        get all domains that are associated with the portfolio, or
        associated with the member/invited member"""

        domain_ids = self._get_domain_ids_from_request(request)

        objects = Domain.objects.filter(id__in=domain_ids).select_related("domain_info__sub_organization")
        unfiltered_total = objects.count()

        objects = self._apply_search(objects, request)
        objects = self._apply_sorting(objects, request)

        paginator = Paginator(objects, self._get_page_size(request))
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        member_id = request.GET.get("member_id")
        domains = [self._serialize_domain(domain, member_id, request.user) for domain in page_obj.object_list]

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

    def _get_page_size(self, request):
        """Gets the page size.

        If member_only, need to return the entire result set every time, so need
        to set to a very large page size. If not member_only, this can be adjusted
        to provide a smaller page size"""

        member_only = request.GET.get("member_only", "false").lower() in ["true", "1"]
        if member_only:
            # This number needs to remain very high as the entire result set
            # must be returned when member_only
            return 1000
        else:
            # This number can be adjusted if we want to add pagination to the result page
            # later
            return 1000

    def _get_domain_ids_from_request(self, request):
        """Get domain ids from request.

        request.get.email - email address of invited member
        request.get.member_id - member id of member
        request.get.portfolio - portfolio id of portfolio
        request.get.member_only - whether to return only domains associated with member
        or to return all domains in the portfolio
        """
        portfolio = request.GET.get("portfolio")
        email = request.GET.get("email")
        member_id = request.GET.get("member_id")
        member_only = request.GET.get("member_only", "false").lower() in ["true", "1"]
        if member_only:
            if member_id:
                member = get_object_or_404(User, pk=member_id)
                domain_info_ids = DomainInformation.objects.filter(portfolio=portfolio).values_list(
                    "domain_id", flat=True
                )
                user_domain_roles = UserDomainRole.objects.filter(user=member).values_list("domain_id", flat=True)
                return domain_info_ids.intersection(user_domain_roles)
            elif email:
                domain_info_ids = DomainInformation.objects.filter(portfolio=portfolio).values_list(
                    "domain_id", flat=True
                )
                domain_invitations = DomainInvitation.objects.filter(
                    email=email, status=DomainInvitation.DomainInvitationStatus.INVITED
                ).values_list("domain_id", flat=True)
                return domain_info_ids.intersection(domain_invitations)
        else:
            domain_infos = DomainInformation.objects.filter(portfolio=portfolio)
            return domain_infos.values_list("domain_id", flat=True)
        logger.warning("Invalid search criteria, returning empty results list")
        return []

    def _apply_search(self, queryset, request):
        search_term = request.GET.get("search_term")
        if search_term:
            queryset = queryset.filter(Q(name__icontains=search_term))
        return queryset

    def _apply_sorting(self, queryset, request):
        # Get the sorting parameters from the request
        sort_by = request.GET.get("sort_by", "name")
        order = request.GET.get("order", "asc")
        # Sort by 'checked' if specified, otherwise by the given field
        if sort_by == "checked":
            # Get list of checked ids from the request
            checked_ids = request.GET.get("checkedDomainIds")
            if checked_ids:
                # Split the comma-separated string into a list of integers
                checked_ids = [int(id.strip()) for id in checked_ids.split(",") if id.strip().isdigit()]
            else:
                # If no value is passed, set checked_ids to an empty list
                checked_ids = []
            # Annotate each object with a 'checked' value based on whether its ID is in checkedIds
            queryset = queryset.annotate(
                checked=models.Case(
                    models.When(id__in=checked_ids, then=models.Value(True)),
                    default=models.Value(False),
                    output_field=models.BooleanField(),
                )
            )
            # Add ordering logic for 'checked'
            if order == "desc":
                queryset = queryset.order_by("-checked", "name")
            else:
                queryset = queryset.order_by("checked", "name")
        else:
            # Handle other fields as normal
            if order == "desc":
                sort_by = f"-{sort_by}"
            queryset = queryset.order_by(sort_by)

        return queryset

    def _serialize_domain(self, domain, member_id, user):
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

        # Check if the specified member is the only member assigned as manager of domain
        only_member_assigned_to_domain = False
        if member_id:
            member_domain_role_count = UserDomainRole.objects.filter(
                domain_id=domain.id, role=UserDomainRole.Roles.MANAGER
            ).count()
            member_domain_role_exists = UserDomainRole.objects.filter(
                domain_id=domain.id, user_id=member_id, role=UserDomainRole.Roles.MANAGER
            ).exists()
            only_member_assigned_to_domain = member_domain_role_exists and member_domain_role_count == 1

        return {
            "id": domain.id,
            "name": domain.name,
            "member_is_only_manager": only_member_assigned_to_domain,
            "expiration_date": domain.expiration_date,
            "state": domain.state,
            "state_display": domain.state_display(),
            "get_state_help_text": domain.get_state_help_text(),
            "action_url": reverse("domain", kwargs={"domain_pk": domain.id}),
            "action_label": ("View" if view_only else "Manage"),
            "svg_icon": ("visibility" if view_only else "settings"),
            "domain_info__sub_organization": suborganization_name,
        }
