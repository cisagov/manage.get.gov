from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Value, F, CharField, TextField, Q, Case, When, OuterRef, Subquery
from django.db.models.expressions import Func
from django.db.models.functions import Cast, Coalesce, Concat
from django.contrib.postgres.aggregates import ArrayAgg
from django.urls import reverse
from django.views import View

from registrar.models import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices
from registrar.utility.model_annotations import PortfolioInvitationModelAnnotation, UserPortfolioPermissionModelAnnotation
from registrar.views.utility.mixins import PortfolioMembersPermission


class PortfolioMembersJson(PortfolioMembersPermission, View):

    def get(self, request):
        """Fetch members (permissions and invitations) for the given portfolio."""

        portfolio = request.GET.get("portfolio")

        # Two initial querysets which will be combined
        permissions = self.initial_permissions_search(portfolio)
        invitations = self.initial_invitations_search(portfolio)

        # Get total across both querysets before applying filters
        unfiltered_total = permissions.count() + invitations.count()

        permissions = self.apply_search_term(permissions, request)
        invitations = self.apply_search_term(invitations, request)

        # Union the two querysets
        objects = permissions.union(invitations)
        objects = self.apply_sorting(objects, request)

        paginator = Paginator(objects, 10)
        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)

        members = [self.serialize_members(portfolio, item, request.user) for item in page_obj.object_list]

        return JsonResponse(
            {
                "members": members,
                "UserPortfolioPermissionChoices": UserPortfolioPermissionChoices.to_dict(),
                "page": page_obj.number,
                "num_pages": paginator.num_pages,
                "has_previous": page_obj.has_previous(),
                "has_next": page_obj.has_next(),
                "total": paginator.count,
                "unfiltered_total": unfiltered_total,
            }
        )

    def initial_permissions_search(self, portfolio):
        """Perform initial search for permissions before applying any filters."""
        queryset = UserPortfolioPermissionModelAnnotation.get_annotated_queryset(portfolio)
        return queryset.values(
            "id",
            "first_name",
            "last_name",
            "email_display",
            "last_active",
            "roles",
            "additional_permissions_display",
            "member_display",
            "domain_info",
            "source",
        )

    def initial_invitations_search(self, portfolio):
        """Perform initial invitations search and get related DomainInvitation data based on the email."""
        # Get DomainInvitation query for matching email and for the portfolio
        queryset = PortfolioInvitationModelAnnotation.get_annotated_queryset(portfolio)
        return queryset.values(
            "id",
            "first_name",
            "last_name",
            "email_display",
            "last_active",
            "roles",
            "additional_permissions_display",
            "member_display",
            "domain_info",
            "source",
        )

    def apply_search_term(self, queryset, request):
        """Apply search term to the queryset."""
        search_term = request.GET.get("search_term", "").lower()
        if search_term:
            queryset = queryset.filter(
                Q(first_name__icontains=search_term)
                | Q(last_name__icontains=search_term)
                | Q(email_display__icontains=search_term)
            )
        return queryset

    def apply_sorting(self, queryset, request):
        """Apply sorting to the queryset."""
        sort_by = request.GET.get("sort_by", "id")  # Default to 'id'
        order = request.GET.get("order", "asc")  # Default to 'asc'
        # Adjust sort_by to match the annotated fields in the unioned queryset
        if sort_by == "member":
            sort_by = "member_display"
        if order == "desc":
            queryset = queryset.order_by(F(sort_by).desc())
        else:
            queryset = queryset.order_by(sort_by)
        return queryset

    def serialize_members(self, portfolio, item, user):
        # Check if the user can edit other users
        user_can_edit_other_users = any(
            user.has_perm(perm) for perm in ["registrar.full_access_permission", "registrar.change_user"]
        )

        view_only = not user.has_edit_members_portfolio_permission(portfolio) or not user_can_edit_other_users

        is_admin = UserPortfolioRoleChoices.ORGANIZATION_ADMIN in (item.get("roles") or [])
        action_url = reverse("member" if item["source"] == "permission" else "invitedmember", kwargs={"pk": item["id"]})

        # Serialize member data
        member_json = {
            "id": item.get("id", ""),
            "source": item.get("source", ""),
            "name": " ".join(filter(None, [item.get("first_name", ""), item.get("last_name", "")])),
            "email": item.get("email_display", ""),
            "member_display": item.get("member_display", ""),
            "roles": (item.get("roles") or []),
            "permissions": UserPortfolioPermission.get_portfolio_permissions(
                item.get("roles"), item.get("additional_permissions_display")
            ),
            # split domain_info array values into ids to form urls, and names
            "domain_urls": [
                reverse("domain", kwargs={"pk": domain_info.split(":")[0]}) for domain_info in item.get("domain_info")
            ],
            "domain_names": [domain_info.split(":")[1] for domain_info in item.get("domain_info")],
            "is_admin": is_admin,
            "last_active": item.get("last_active"),
            "action_url": action_url,
            "action_label": ("View" if view_only else "Manage"),
            "svg_icon": ("visibility" if view_only else "settings"),
        }
        return member_json
