from django.http import JsonResponse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.db.models import Q

from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.user import User
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioRoleChoices


@login_required
def get_portfolio_members_json(request):
    """Given the current request,
    get all members that are associated with the given portfolio"""
    portfolio = request.GET.get("portfolio")
    member_ids = get_member_ids_from_request(request, portfolio)
    objects = User.objects.filter(id__in=member_ids)

    admin_ids = UserPortfolioPermission.objects.filter(
        portfolio=portfolio,
        roles__overlap=[
            UserPortfolioRoleChoices.ORGANIZATION_ADMIN,
        ],
    ).values_list("user__id", flat=True)
    portfolio_invitation_emails = PortfolioInvitation.objects.filter(portfolio=portfolio).values_list(
        "email", flat=True
    )

    unfiltered_total = objects.count()

    objects = apply_search(objects, request)
    # objects = apply_status_filter(objects, request)
    objects = apply_sorting(objects, request)

    paginator = Paginator(objects, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)
    members = [
        serialize_members(request, portfolio, member, request.user, admin_ids, portfolio_invitation_emails)
        for member in page_obj.object_list
    ]

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


def get_member_ids_from_request(request, portfolio):
    """Given the current request,
    get all members that are associated with the given portfolio"""
    member_ids = []
    if portfolio:
        member_ids = UserPortfolioPermission.objects.filter(portfolio=portfolio).values_list("user__id", flat=True)
    return member_ids


def apply_search(queryset, request):
    search_term = request.GET.get("search_term")

    if search_term:
        queryset = queryset.filter(
            Q(username__icontains=search_term)
            | Q(first_name__icontains=search_term)
            | Q(last_name__icontains=search_term)
            | Q(email__icontains=search_term)
        )
    return queryset


def apply_sorting(queryset, request):
    sort_by = request.GET.get("sort_by", "id")  # Default to 'id'
    order = request.GET.get("order", "asc")  # Default to 'asc'

    if order == "desc":
        sort_by = f"-{sort_by}"
    return queryset.order_by(sort_by)


def serialize_members(request, portfolio, member, user, admin_ids, portfolio_invitation_emails):
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
    is_invited = member.email in portfolio_invitation_emails
    last_active = "Invited" if is_invited else "Unknown"
    if member.last_login:
        last_active = member.last_login.strftime("%b. %d, %Y")
    is_admin = member.id in admin_ids

    # ------- SERIALIZE
    member_json = {
        "id": member.id,
        "name": member.get_formatted_name(),
        "email": member.email,
        "is_admin": is_admin,
        "last_active": last_active,
        "action_url": "#",  # reverse("members", kwargs={"pk": member.id}), # TODO: Future ticket?
        "action_label": ("View" if view_only else "Manage"),
        "svg_icon": ("visibility" if view_only else "settings"),
    }
    return member_json
