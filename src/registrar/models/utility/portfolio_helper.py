from django.db import models


class UserPortfolioRoleChoices(models.TextChoices):
    """
    Roles make it easier for admins to look at
    """

    ORGANIZATION_ADMIN = "organization_admin", "Admin"
    # ORGANIZATION_ADMIN_READ_ONLY = "organization_admin_read_only", "Admin read only"
    ORGANIZATION_MEMBER = "organization_member", "Member"


class UserPortfolioPermissionChoices(models.TextChoices):
    """ """

    VIEW_ALL_DOMAINS = "view_all_domains", "View all domains and domain reports"
    VIEW_MANAGED_DOMAINS = "view_managed_domains", "View managed domains"

    VIEW_MEMBERS = "view_members", "View members"
    EDIT_MEMBERS = "edit_members", "Create and edit members"

    VIEW_ALL_REQUESTS = "view_all_requests", "View all requests"
    EDIT_REQUESTS = "edit_requests", "Create and edit requests"

    VIEW_PORTFOLIO = "view_portfolio", "View organization"
    EDIT_PORTFOLIO = "edit_portfolio", "Edit organization"

    # Domain: field specific permissions
    VIEW_SUBORGANIZATION = "view_suborganization", "View suborganization"
    EDIT_SUBORGANIZATION = "edit_suborganization", "Edit suborganization"
