from django.http import JsonResponse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.db.models import Value, F, CharField, TextField, Q, Case, When
from django.db.models.functions import Concat, Coalesce
from django.urls import reverse
from django.db.models.functions import Cast

from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioRoleChoices


@login_required
def get_portfolio_members_json(request):
    """Fetch members (permissions and invitations) for the given portfolio."""

    portfolio = request.GET.get("portfolio")

    # Two initial querysets which will be combined
    permissions = initial_permissions_search(portfolio)
    invitations = initial_invitations_search(portfolio)

    # Get total across both querysets before applying filters
    unfiltered_total = permissions.count() + invitations.count()

    permissions = apply_search_term(permissions, request)
    invitations = apply_search_term(permissions, request)

    # Union the two querysets
    objects = permissions.union(invitations)
    objects = apply_sorting(objects, request)

    paginator = Paginator(objects, 10)
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
            "unfiltered_total": unfiltered_total,
        }
    )


def initial_permissions_search(portfolio):
    """Perform initial search for permissions before applying any filters."""
    permissions = UserPortfolioPermission.objects.filter(portfolio=portfolio)
    permissions = (
        permissions.select_related("user")
        .annotate(
            first_name=F("user__first_name"),
            last_name=F("user__last_name"),
            email_display=F("user__email"),
            last_active=Cast(F("user__last_login"), output_field=TextField()),  # Cast last_login to text
            roles_display=F("roles"),
            additional_permissions_display=F("additional_permissions"),
            member_sort_value=Case(
                # If email is present and not blank, use email
                When(Q(user__email__isnull=False) & ~Q(user__email=""), then=F("user__email")),
                # If first name or last name is present, use concatenation of first_name + " " + last_name
                When(
                    Q(user__first_name__isnull=False) | Q(user__last_name__isnull=False),
                    then=Concat(
                        Coalesce(F("user__first_name"), Value("")),
                        Value(" "),
                        Coalesce(F("user__last_name"), Value("")),
                    ),
                ),
                # If neither, use an empty string
                default=Value(""),
                output_field=CharField(),
            ),
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
            "member_sort_value",
            "source",
        )
    )
    return permissions


def initial_invitations_search(portfolio):
    """Perform initial invitations search before applying any filters."""
    invitations = PortfolioInvitation.objects.filter(portfolio=portfolio)
    invitations = invitations.annotate(
        first_name=Value(None, output_field=CharField()),
        last_name=Value(None, output_field=CharField()),
        email_display=F("email"),
        last_active=Value("Invited", output_field=TextField()),
        roles_display=F("roles"),
        additional_permissions_display=F("additional_permissions"),
        member_sort_value=F("email"),
        source=Value("invitation", output_field=CharField()),
    ).values(
        "id",
        "first_name",
        "last_name",
        "email_display",
        "last_active",
        "roles_display",
        "additional_permissions_display",
        "member_sort_value",
        "source",
    )
    return invitations


def apply_search_term(queryset, request):
    """Apply search term to the queryset."""
    search_term = request.GET.get("search_term", "").lower()
    if search_term:
        queryset = queryset.filter(
            Q(first_name__icontains=search_term)
            | Q(last_name__icontains=search_term)
            | Q(email_display__icontains=search_term)
        )
    return queryset


def apply_sorting(queryset, request):
    """Apply sorting to the queryset."""
    sort_by = request.GET.get("sort_by", "id")  # Default to 'id'
    order = request.GET.get("order", "asc")  # Default to 'asc'
    # Adjust sort_by to match the annotated fields in the unioned queryset
    if sort_by == "member":
        sort_by = "member_sort_value"
    if order == "desc":
        queryset = queryset.order_by(F(sort_by).desc())
    else:
        queryset = queryset.order_by(sort_by)
    return queryset


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
        "member_sort_value": item.get("member_sort_value", ""),
        "is_admin": is_admin,
        "last_active": item.get("last_active", ""),
        "action_url": action_url,
        "action_label": ("View" if view_only else "Manage"),
        "svg_icon": ("visibility" if view_only else "settings"),
    }
    return member_json
