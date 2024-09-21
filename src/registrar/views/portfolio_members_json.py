from django.http import JsonResponse
from django.core.paginator import Paginator
from registrar.models import DomainRequest
from django.utils.dateformat import format
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.db.models import Q

from registrar.models.user_portfolio_permission import UserPortfolioPermission


# DEVELOPER'S NOTE (9-20-24):
# The way this works is first we get a list of "member" objects
# Then we pass this to "serialize_members", which extracts object information
# and puts it into a JSON that is then used in get-gov.js for dynamically
# populating the frontend members table with data.  
# So, if you're wondering where these JSON values are used, check out the class "MembersTable"
# in get-gov.js (specifically the "loadTable" function).
#
# The way get-gov.js grabs this JSON is via the html.  Specifically,
# "get_portfolio_members_json" is embedded in members_table.html as a string, which 
# is then referenced in get-gov.js. This path is also added to urls.py.


@login_required
def get_portfolio_members_json(request):
    """Given the current request,
    get all members that are associated with the given portfolio"""

    member_ids = get_member_ids_from_request(request)
    unfiltered_total = member_ids.count()

    objects = UserPortfolioPermission.objects.filter(id__in=member_ids)
    unfiltered_total = objects.count()

    # objects = apply_search(objects, request)
    # objects = apply_status_filter(objects, request)
    # objects = apply_sorting(objects, request)

    paginator = Paginator(objects, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)
    members = [
        serialize_members(request, member, request.user) for member in page_obj.object_list
    ]

    return JsonResponse(
        {
            "members": members, # "domain_requests": domain_requests,  TODO: DELETE ME!
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
            "page": page_obj.number,
            "num_pages": paginator.num_pages,
            "total": paginator.count,
            "unfiltered_total": unfiltered_total,
        }
    )


def get_member_ids_from_request(request):
    """Given the current request,
    get all members that are associated with the given portfolio"""
    portfolio = request.GET.get("portfolio")
    # filter_condition = Q(creator=request.user)
    if portfolio:
        # TODO: Permissions??
        # if request.user.is_org_user(request) and request.user.has_view_all_requests_portfolio_permission(portfolio):
        #     filter_condition = Q(portfolio=portfolio)
        # else:
        #     filter_condition = Q(portfolio=portfolio, creator=request.user)

        member_ids = UserPortfolioPermission.objects.filter(
                portfolio=portfolio
            ).values_list("user__id", flat=True)
        return member_ids


# def apply_search(queryset, request):
#     search_term = request.GET.get("search_term")
#     is_portfolio = request.GET.get("portfolio")

#     if search_term:
#         search_term_lower = search_term.lower()
#         new_domain_request_text = "new domain request"

#         # Check if the search term is a substring of 'New domain request'
#         # If yes, we should return domain requests that do not have a
#         # requested_domain (those display as New domain request in the UI)
#         if search_term_lower in new_domain_request_text:
#             queryset = queryset.filter(
#                 Q(requested_domain__name__icontains=search_term) | Q(requested_domain__isnull=True)
#             )
#         elif is_portfolio:
#             queryset = queryset.filter(
#                 Q(requested_domain__name__icontains=search_term)
#                 | Q(creator__first_name__icontains=search_term)
#                 | Q(creator__last_name__icontains=search_term)
#                 | Q(creator__email__icontains=search_term)
#             )
#         # For non org users
#         else:
#             queryset = queryset.filter(Q(requested_domain__name__icontains=search_term))
#     return queryset


# def apply_status_filter(queryset, request):
#     status_param = request.GET.get("status")
#     if status_param:
#         status_list = status_param.split(",")
#         statuses = [status for status in status_list if status in DomainRequest.DomainRequestStatus.values]
#         # Construct Q objects for statuses that can be queried through ORM
#         status_query = Q()
#         if statuses:
#             status_query |= Q(status__in=statuses)
#         # Apply the combined query
#         queryset = queryset.filter(status_query)

#     return queryset


# def apply_sorting(queryset, request):
#     sort_by = request.GET.get("sort_by", "id")  # Default to 'id'
#     order = request.GET.get("order", "asc")  # Default to 'asc'

#     if order == "desc":
#         sort_by = f"-{sort_by}"
#     return queryset.order_by(sort_by)


def serialize_members(request, member, user):

# ------- DELETABLE
#     deletable_statuses = [
#         DomainRequest.DomainRequestStatus.STARTED,
#         DomainRequest.DomainRequestStatus.WITHDRAWN,
#     ]

#     # Determine if the request is deletable
#     if not user.is_org_user(request):
#         is_deletable = member.status in deletable_statuses
#     else:
#         portfolio = request.session.get("portfolio")
#         is_deletable = (
#             member.status in deletable_statuses and user.has_edit_request_portfolio_permission(portfolio)
#         ) and member.creator == user


# ------- EDIT / VIEW
#     # Determine action label based on user permissions and request status
#     editable_statuses = [
#         DomainRequest.DomainRequestStatus.STARTED,
#         DomainRequest.DomainRequestStatus.ACTION_NEEDED,
#         DomainRequest.DomainRequestStatus.WITHDRAWN,
#     ]

#     if user.has_edit_request_portfolio_permission and member.creator == user:
#         action_label = "Edit" if member.status in editable_statuses else "Manage"
#     else:
#         action_label = "View"

#     # Map the action label to corresponding URLs and icons
#     action_url_map = {
#         "Edit": reverse("edit-domain-request", kwargs={"id": member.id}),
#         "Manage": reverse("domain-request-status", kwargs={"pk": member.id}),
#         "View": "#",
#     }

#     svg_icon_map = {"Edit": "edit", "Manage": "settings", "View": "visibility"}


# ------- INVITED
# TODO:....


# ------- SERIALIZE

    return {
        "id": member.id,
        # "name": ??,
        # "last_active": ??,
        # ("manage icon...maybe svg_icon??")
    }

#  return {
#         "id": domain.id,
#         "name": domain.name,
#         "expiration_date": domain.expiration_date,
#         "state": domain.state,
#         "state_display": domain.state_display(),
#         "get_state_help_text": domain.get_state_help_text(),
#         "action_url": reverse("domain", kwargs={"pk": domain.id}),
#         "action_label": ("View" if view_only else "Manage"),
#         "svg_icon": ("visibility" if view_only else "settings"),
#         "domain_info__sub_organization": suborganization_name,
#     }
