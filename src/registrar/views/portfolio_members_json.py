
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils import timezone
from django.db.models import Q

from registrar.models.portfolio_invitation import PortfolioInvitation
from registrar.models.user import User
from registrar.models.user_portfolio_permission import UserPortfolioPermission

#---Logger
import logging
from venv import logger
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper
from registrar.models.utility.portfolio_helper import UserPortfolioRoleChoices
logger = logging.getLogger(__name__)


@login_required
def get_portfolio_members_json(request):
    """Given the current request,
    get all members that are associated with the given portfolio"""

    objects = get_member_objects_from_request(request)
    if(objects is not None):
        member_ids = objects.values_list("id", flat=True)

        portfolio = request.session.get("portfolio")
        admin_ids = UserPortfolioPermission.objects.filter(
                portfolio=portfolio,
                roles__overlap=[
                    UserPortfolioRoleChoices.ORGANIZATION_ADMIN,
                ],
            ).values_list("user__id", flat=True)
        portfolio_invitation_emails = PortfolioInvitation.objects.filter(portfolio=portfolio).values_list("email", flat=True)
       
        
        unfiltered_total = member_ids.count()

        objects = apply_search(objects, request)
        # objects = apply_status_filter(objects, request)
        # objects = apply_sorting(objects, request)

        paginator = Paginator(objects, 10)
        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)
        members = [
            serialize_members(request, member, request.user, admin_ids, portfolio_invitation_emails) for member in page_obj.object_list
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

        permissions = UserPortfolioPermission.objects.filter(
                portfolio=portfolio
            )
        
        portfolio_invitation_emails = PortfolioInvitation.objects.filter(portfolio=portfolio).values_list("email", flat=True)
        
        members = User.objects.filter(Q(portfolio_permissions__in=permissions) | Q(email__in=portfolio_invitation_emails))
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




# TODO: delete these...(failed experiment)
# def get_admin_members(request):
#         portfolio = request.GET.get("portfolio")
#         # Filter UserPortfolioPermission objects related to the portfolio
#         admin_permissions = UserPortfolioPermission.objects.filter(
#             portfolio=portfolio, roles__contains=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
#         )

#         # Get the user objects associated with these permissions
#         admin_users = User.objects.filter(portfolio_permissions__in=admin_permissions)

#         return admin_users

# def get_non_admin_members(request):
#     portfolio = request.GET.get("portfolio")
#     # Filter UserPortfolioPermission objects related to the portfolio that do NOT have the "Admin" role
#     non_admin_permissions = UserPortfolioPermission.objects.filter(portfolio=portfolio).exclude(
#         roles__contains=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN]
#     )

#     # Get the user objects associated with these permissions
#     non_admin_users = User.objects.filter(portfolio_permissions__in=non_admin_permissions)

#     return non_admin_users


def serialize_members(request, member, user, admin_ids, portfolio_invitation_emails):

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

    # ------- USER STATUS
    is_invited = member.email in portfolio_invitation_emails
    last_active = "Invited" if is_invited else "Unknown"
    if member.last_login:
        last_active = member.last_login.strftime("%b. %d, %Y")


    # portfolio = request.session.get("portfolio")
    # roles = member.portfolio_role_summary(portfolio)
    # TerminalHelper.colorful_logger(logger.info, TerminalColors.OKGREEN, f'roles {roles}')  # TODO: delete me
    # is_admin = 'Admin' in roles # TODO: use enums? Is there a better way to grab this?

    # is_admin = member.has_edit_suborganization_portfolio_permission(portfolio) 
    # is_admin = member._has_portfolio_permission(portfolio, UserPortfolioRoleChoices.ORGANIZATION_ADMIN)

    is_admin = member.id in admin_ids


    # ------- SERIALIZE
    return {
        "id": member.id,
        "name": member.get_formatted_name(),
        "email": member.email,
        "is_admin": is_admin,
        "last_active": last_active,
        "action_url": '#', #reverse("members", kwargs={"pk": member.id}), #TODO: Future ticket?
        "action_label": ("View" if view_only else "Manage"),
        "svg_icon": ("visibility" if view_only else "settings"),
    }
