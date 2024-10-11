from django.http import JsonResponse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.db.models import Value, F, CharField, TextField, Q
from django.urls import reverse
from django.db.models.functions import Cast

from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioRoleChoices


@login_required
def get_portfolio_members_json(request):
    """Fetch members (permissions and invitations) for the given portfolio."""
    portfolio = request.GET.get("portfolio")
    search_term = request.GET.get("search_term", "").lower()

    # Permissions queryset
    permissions = UserPortfolioPermission.objects.filter(portfolio=portfolio)

    if search_term:
        permissions = permissions.filter(
            Q(user__first_name__icontains=search_term)
            | Q(user__last_name__icontains=search_term)
            | Q(user__email__icontains=search_term)
        )

    permissions = (
        permissions.select_related("user")
        .annotate(
            first_name=F("user__first_name"),
            last_name=F("user__last_name"),
            email_display=F("user__email"),
            last_active=Cast(F("user__last_login"), output_field=TextField()),  # Cast last_login to text
            roles_display=F("roles"),
            additional_permissions_display=F("additional_permissions"),
            source=Value("permission", output_field=CharField()),
        )
        .values(
            "id",
            "first_name",
            "last_name",
            "email_display",
            "last_active",
            "roles_display",
            "additional_permissions_display",
            "source",
        )
    )

    # Invitations queryset
    invitations = PortfolioInvitation.objects.filter(portfolio=portfolio)

    if search_term:
        invitations = invitations.filter(Q(email__icontains=search_term))

    invitations = invitations.annotate(
        first_name=Value(None, output_field=CharField()),
        last_name=Value(None, output_field=CharField()),
        email_display=F("email"),
        last_active=Value("Invited", output_field=TextField()),  # Use "Invited" as a text value
        roles_display=F("roles"),
        additional_permissions_display=F("additional_permissions"),
        source=Value("invitation", output_field=CharField()),
    ).values(
        "id",
        "first_name",
        "last_name",
        "email_display",
        "last_active",
        "roles_display",
        "additional_permissions_display",
        "source",
    )

    # Union the two querysets after applying search filters
    combined_queryset = permissions.union(invitations)

    # Apply sorting
    sort_by = request.GET.get("sort_by", "id")  # Default to 'id'
    order = request.GET.get("order", "asc")  # Default to 'asc'

    # Adjust sort_by to match the annotated fields in the unioned queryset
    if sort_by == "member":
        sort_by = "email_display"  # Use email_display instead of email

    if order == "desc":
        combined_queryset = combined_queryset.order_by(F(sort_by).desc())
    else:
        combined_queryset = combined_queryset.order_by(sort_by)

    paginator = Paginator(combined_queryset, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    members = [serialize_members(request, portfolio, item, request.user) for item in page_obj.object_list]

    return JsonResponse(
        {
            "members": members,
            "page": page_obj.number,
            "num_pages": paginator.num_pages,
            "has_previous": page_obj.has_previous(),
            "has_next": page_obj.has_next(),
            "total": paginator.count,
            "unfiltered_total": combined_queryset.count(),
        }
    )


def serialize_members(request, portfolio, item, user):
    # Check if the user can edit other users
    user_can_edit_other_users = any(
        user.has_perm(perm) for perm in ["registrar.full_access_permission", "registrar.change_user"]
    )

    view_only = not user.has_edit_members_portfolio_permission(portfolio) or not user_can_edit_other_users

    is_admin = UserPortfolioRoleChoices.ORGANIZATION_ADMIN in item.get("roles_display", [])
    action_url = reverse("member" if item["source"] == "permission" else "invitedmember", kwargs={"pk": item["id"]})

    # Serialize member data
    member_json = {
        "id": item.get("id", ""),
        "name": " ".join(filter(None, [item.get("first_name", ""), item.get("last_name", "")])),
        "email": item.get("email_display", ""),
        "is_admin": is_admin,
        "last_active": item.get("last_active", ""),
        "action_url": action_url,
        "action_label": ("View" if view_only else "Manage"),
        "svg_icon": ("visibility" if view_only else "settings"),
    }
    return member_json
