
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils import timezone
from django.db.models import Q

from registrar.models.user import User
from registrar.models.user_portfolio_permission import UserPortfolioPermission

#---Logger
import logging
from venv import logger
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper
logger = logging.getLogger(__name__)


@login_required
def get_portfolio_members_json(request):
    """Given the current request,
    get all members that are associated with the given portfolio"""

    objects = get_member_objects_from_request(request)
    if(objects is not None):
        member_ids = objects.values_list("id", flat=True)
        unfiltered_total = member_ids.count()

        objects = apply_search(objects, request)
        # objects = apply_status_filter(objects, request)
        # objects = apply_sorting(objects, request)

        paginator = Paginator(objects, 10)
        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)
        members = [
            serialize_members(request, member, request.user) for member in page_obj.object_list
        ]

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
        return JsonResponse(
            {
                "members": members,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
                "page": page_obj.number,
                "num_pages": paginator.num_pages,
                "total": paginator.count,
                "unfiltered_total": unfiltered_total,
            }
        )
    
    else:
        # TODO: clean this up -- this was added to handle NoneType error (test with http://localhost:8080/get-portfolio-members-json/)
        # Perhaps this is why domain_requests_json does the wierd thing where it returns deomain request ids, then re-fetches the objects...
        # Or maybe an assumption was made wherein we assume there will never be zero entries returned??
        return JsonResponse(
            {
                "members": [],
                "has_next": False,
                "has_previous": False,
                "page": 0,
                "num_pages": 0,
                "total": 0,
                "unfiltered_total": 0,
            }
        )


def get_member_objects_from_request(request):
    """Given the current request,
    get all members that are associated with the given portfolio"""

    # portfolio = request.GET.get("portfolio") #TODO: WHY DOESN"T THIS WORK?? It is empty
    # TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, f'portfolio = {portfolio}')  # TODO: delete me

    portfolio = request.session.get("portfolio")

    if portfolio:
        # TODO: Permissions??
        # if request.user.is_org_user(request) and request.user.has_view_all_requests_portfolio_permission(portfolio):
        #     filter_condition = Q(portfolio=portfolio)
        # else:
        #     filter_condition = Q(portfolio=portfolio, creator=request.user)

        TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, "getting permissions")  # TODO: delete me
        permissions = UserPortfolioPermission.objects.filter(
                portfolio=portfolio
            )
       
        TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, f'permissions {permissions}')  # TODO: delete me
        members = User.objects.filter(portfolio_permissions__in=permissions)
        TerminalHelper.colorful_logger(logger.info, TerminalColors.OKCYAN, f'members {members}')  # TODO: delete me
        return members


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


    # ------- VIEW ONLY
    # Determine action label based on user permissions
    # If the user has permissions to edit/manage users, show the gear icon with "Manage" link. 
    # If the user has view user permissions only, show the "View" link (no gear icon).
    view_only = not user.has_edit_members_portfolio_permission

    # ------- ACTIVITY
    is_invited = member.verification_type == User.VerificationTypeChoices.INVITED
    last_active = "invited" if is_invited else "unknown"
    if member.last_login:
        last_active = member.last_login.strftime("%b. %d, %Y")

    # ------- SERIALIZE
    return {
        "id": member.id,
        "name": member.get_formatted_name(),
        "email": member.email,
        "last_active": last_active,
        "action_url": '#', #reverse("members", kwargs={"pk": member.id}), #TODO: Future ticket?
        "action_label": ("View" if view_only else "Manage"),
        "svg_icon": ("visibility" if view_only else "settings"),
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
