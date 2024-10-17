from django.http import JsonResponse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.db.models import Value, F, CharField, TextField, Q, Case, When, OuterRef, Subquery
from django.db.models.functions import Concat, Coalesce
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.aggregates import ArrayAgg
from django.urls import reverse
from django.db.models.functions import Cast

from registrar.models.domain_invitation import DomainInvitation
from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices


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
    invitations = apply_search_term(invitations, request)

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
            "UserPortfolioPermissionChoices": UserPortfolioPermissionChoices.to_dict(),
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
            member_display=Case(
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
            domain_info=ArrayAgg(
                # an array of domains, with id and name, colon separated
                Concat(
                    F("user__permissions__domain_id"),
                    Value(":"),
                    F("user__permissions__domain__name"),
                    # specify the output_field to ensure union has same column types
                    output_field=CharField(),
                ),
                distinct=True,
                filter=Q(user__permissions__domain__isnull=False),
            ),
            source=Value("permission", output_field=CharField()),
        )
        .values(
            "id",
            "first_name",
            "last_name",
            "email_display",
            "last_active",
            "roles",
            "additional_permissions",
            "member_display",
            "domain_info",
            "source",
        )
    )
    return permissions


def initial_invitations_search(portfolio):
    """Perform initial invitations search and get related DomainInvitation data based on the email."""
    # Get DomainInvitation query for matching email
    domain_invitations = DomainInvitation.objects.filter(email=OuterRef("email"), domain__isnull=False).annotate(
        domain_info=Concat(F("domain__id"), Value(":"), F("domain__name"), output_field=CharField())
    )
    invitations = PortfolioInvitation.objects.filter(portfolio=portfolio)
    invitations = invitations.annotate(
        first_name=Value(None, output_field=CharField()),
        last_name=Value(None, output_field=CharField()),
        email_display=F("email"),
        last_active=Value("Invited", output_field=TextField()),
        member_display=F("email"),
        # ArrayAgg for multiple domain_invitations matched by email, filtered to exclude nulls
        domain_info=Coalesce(  # Use Coalesce to return an empty list if no domain invitations exist
            ArrayAgg(
                Subquery(domain_invitations.values("domain_info")),
                distinct=True,
            ),
            Value([], output_field=ArrayField(CharField())),  # Ensure we return an empty list
        ),
        source=Value("invitation", output_field=CharField()),
    ).values(
        "id",
        "first_name",
        "last_name",
        "email_display",
        "last_active",
        "roles",
        "additional_permissions",
        "member_display",
        "domain_info",
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
        sort_by = "member_display"
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
            item.get("roles"), item.get("additional_permissions")
        ),
        "domain_names": [
            domain_info.split(":")[1]
            for domain_info in (item.get("domain_info") or [])
            if domain_info is not None  # Prevent splitting None
        ],
        "domain_urls": [
            reverse("domain", kwargs={"pk": domain_info.split(":")[0]})
            for domain_info in (item.get("domain_info") or [])
            if domain_info is not None  # Prevent splitting None
        ],
        "is_admin": is_admin,
        "last_active": item.get("last_active", ""),
        "action_url": action_url,
        "action_label": ("View" if view_only else "Manage"),
        "svg_icon": ("visibility" if view_only else "settings"),
    }
    return member_json
