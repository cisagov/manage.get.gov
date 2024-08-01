from django.db import models


class UserPortfolioRoleChoices(models.TextChoices):
    """
    Roles make it easier for admins to look at
    """

    ORGANIZATION_ADMIN = "organization_admin", "Admin"
    ORGANIZATION_ADMIN_READ_ONLY = "organization_admin_read_only", "Admin read only"
    ORGANIZATION_MEMBER = "organization_member", "Member"


class UserPortfolioPermissionChoices(models.TextChoices):
    """ """

    VIEW_ALL_DOMAINS = "view_all_domains", "View all domains and domain reports"
    VIEW_MANAGED_DOMAINS = "view_managed_domains", "View managed domains"
    # EDIT_DOMAINS is really self.domains. We add is hear and leverage it in has_permission
    # so we have one way to test for portfolio and domain edit permissions
    # Do we need to check for portfolio domains specifically?
    # NOTE: A user on an org can currently invite a user outside the org
    EDIT_DOMAINS = "edit_domains", "User is a manager on a domain"

    VIEW_MEMBER = "view_member", "View members"
    EDIT_MEMBER = "edit_member", "Create and edit members"

    VIEW_ALL_REQUESTS = "view_all_requests", "View all requests"
    VIEW_CREATED_REQUESTS = "view_created_requests", "View created requests"
    EDIT_REQUESTS = "edit_requests", "Create and edit requests"

    VIEW_PORTFOLIO = "view_portfolio", "View organization"
    EDIT_PORTFOLIO = "edit_portfolio", "Edit organization"
