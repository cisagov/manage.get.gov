from datetime import datetime
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.urls import reverse

from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioRoleChoices


@login_required
def get_portfolio_members_json(request):
    """Given the current request,
    get all members that are associated with the given portfolio"""
    portfolio = request.GET.get("portfolio")

    permissions = (
        UserPortfolioPermission.objects.filter(portfolio=portfolio)
        .select_related("user")
        .values_list("pk", "user__first_name", "user__last_name", "user__email", "user__last_login", "roles")
    )
    invitations = PortfolioInvitation.objects.filter(portfolio=portfolio).values_list(
        "pk", "email", "roles", "additional_permissions", "status"
    )

    # Convert the permissions queryset into a list of dictionaries
    permission_list = [
        {
            "id": perm[0],
            "first_name": perm[1],
            "last_name": perm[2],
            "email": perm[3],
            "last_active": perm[4],
            "roles": perm[5],
            "source": "permission",  # Mark the source as permissions
        }
        for perm in permissions
    ]

    # Convert the invitations queryset into a list of dictionaries
    invitation_list = [
        {
            "id": invite[0],
            "first_name": None,  # No first name in invitations
            "last_name": None,  # No last name in invitations
            "email": invite[1],
            "roles": invite[2],
            "additional_permissions": invite[3],
            "status": invite[4],
            "last_active": "Invited",
            "source": "invitation",  # Mark the source as invitations
        }
        for invite in invitations
    ]

    # Combine both lists into one unified list
    combined_list = permission_list + invitation_list

    unfiltered_total = len(combined_list)

    combined_list = apply_search(combined_list, request)
    combined_list = apply_sorting(combined_list, request)

    paginator = Paginator(combined_list, 10)
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


def apply_search(data_list, request):
    search_term = request.GET.get("search_term", "").lower()

    if search_term:
        # Filter the list based on the search term (case-insensitive)
        data_list = [
            item
            for item in data_list
            if item.get("first_name", "")
            and search_term in item.get("first_name", "").lower()
            or item.get("last_name", "")
            and search_term in item.get("last_name", "").lower()
            or item.get("email", "")
            and search_term in item.get("email", "").lower()
        ]

    return data_list


def apply_sorting(data_list, request):
    sort_by = request.GET.get("sort_by", "id")  # Default to 'id'
    order = request.GET.get("order", "asc")  # Default to 'asc'

    if sort_by == "member":
        sort_by = "email"

    # Custom key function that handles None, 'Invited', and datetime values for last_active
    def sort_key(item):
        value = item.get(sort_by)
        if sort_by == "last_active":
            # Return a tuple to ensure consistent data types for comparison
            # First element: ordering value (0 for valid datetime, 1 for 'Invited', 2 for None)
            # Second element: the actual value to sort by
            if value is None:
                return (2, value)  # Position None last
            if value == "Invited":
                return (1, value)  # Position 'Invited' before None but after valid datetimes
            if isinstance(value, datetime):
                return (0, value)  # Position valid datetime values first

        # Default case: return the value as is for comparison
        return value

    # Sort the list using the custom key function
    data_list = sorted(data_list, key=sort_key, reverse=(order == "desc"))

    return data_list


def serialize_members(request, portfolio, item, user):
    # ------- VIEW ONLY
    # If not view_only (the user has permissions to edit/manage users), show the gear icon with "Manage" link.
    # If view_only (the user only has view user permissions), show the "View" link (no gear icon).
    # We check on user_group_permision to account for the upcoming "Manage portfolio" button on admin.
    user_can_edit_other_users = False
    for user_group_permission in ["registrar.full_access_permission", "registrar.change_user"]:
        if user.has_perm(user_group_permission):
            user_can_edit_other_users = True
            break

    view_only = not user.has_edit_members_portfolio_permission(portfolio) or not user_can_edit_other_users

    # ------- USER STATUSES
    is_admin = False
    if item["roles"]:
        is_admin = UserPortfolioRoleChoices.ORGANIZATION_ADMIN in item["roles"]

    action_url = "#"
    if item["source"] == "permission":
        action_url = reverse("member", kwargs={"pk": item["id"]})
    elif item["source"] == "invitation":
        action_url = reverse("invitedmember", kwargs={"pk": item["id"]})

    # ------- SERIALIZE
    member_json = {
        "id": item.get("id", ""),
        "name": " ".join(filter(None, [item.get("first_name", ""), item.get("last_name", "")])),
        "email": item.get("email", ""),
        "is_admin": is_admin,
        "last_active": item.get("last_active", None),
        "action_url": action_url,
        "action_label": ("View" if view_only else "Manage"),
        "svg_icon": ("visibility" if view_only else "settings"),
    }
    return member_json
