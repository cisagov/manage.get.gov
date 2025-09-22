from django.conf import settings


def language_code(request):
    """Add LANGUAGE_CODE to the template context.

    The <html> element of a web page should include a lang="..." attribute. In
    Django, the correct thing to put in that attribute is the value of
    settings.LANGUAGE_CODE but the template context can't access that value
    unless we add it here (and configure this context processor in the
    TEMPLATES dict of our settings file).
    """
    return {"LANGUAGE_CODE": settings.LANGUAGE_CODE}


def canonical_path(request):
    """Add a canonical URL to the template context.

    To make a correct "rel=canonical" link in the HTML page, we need to
    construct an absolute URL for the page, and we can't do that in the
    template itself, so we do it here and pass the information on.
    """
    return {"CANONICAL_PATH": request.build_absolute_uri(request.path)}


def is_demo_site(request):
    """Add a boolean if this is a demo site.

    To be able to render or not our "demo site" banner, we need a context
    variable for the template that indicates if this banner should or
    should not appear.
    """
    return {"IS_DEMO_SITE": settings.IS_DEMO_SITE}


def is_production(request):
    """Add a boolean if this is our production site."""
    return {"IS_PRODUCTION": settings.IS_PRODUCTION}


def org_user_status(request):
    is_org_user = False
    if request.user.is_authenticated:
        is_org_user = request.user.is_org_user(request)

    return {
        "is_org_user": is_org_user,
    }


def add_path_to_context(request):
    return {"path": getattr(request, "path", None)}


def portfolio_permissions(request):
    """Make portfolio permissions for the request user available in global context"""
    portfolio_context = {
        "has_view_portfolio_permission": False,
        "has_edit_portfolio_permission": False,
        "has_any_domains_portfolio_permission": False,
        "has_any_requests_portfolio_permission": False,
        "has_edit_request_portfolio_permission": False,
        "has_view_members_portfolio_permission": False,
        "has_edit_members_portfolio_permission": False,
        "portfolio": None,
        "is_portfolio_user": False,
        "is_portfolio_admin": False,
        "has_multiple_portfolios": False,
    }
    try:
        portfolio = request.session.get("portfolio")
        if portfolio:
            return {
                "has_view_portfolio_permission": request.user.has_view_portfolio_permission(portfolio),
                "has_edit_portfolio_permission": request.user.has_edit_portfolio_permission(portfolio),
                "has_edit_request_portfolio_permission": request.user.has_edit_request_portfolio_permission(portfolio),
                "has_any_domains_portfolio_permission": request.user.has_any_domains_portfolio_permission(portfolio),
                "has_any_requests_portfolio_permission": request.user.has_any_requests_portfolio_permission(portfolio),
                "has_view_members_portfolio_permission": request.user.has_view_members_portfolio_permission(portfolio),
                "has_edit_members_portfolio_permission": request.user.has_edit_members_portfolio_permission(portfolio),
                "portfolio": portfolio,
                "is_portfolio_user": True,
                "is_portfolio_admin": request.user.is_portfolio_admin(portfolio),
                "has_multiple_portfolios": request.user.is_multiple_orgs_user(request),
            }
        # Active portfolio may not be set yet, but indicate if user is a member of multiple portfolios
        portfolio_context["has_multiple_portfolios"] = request.user.is_multiple_orgs_user(request)
        return portfolio_context

    except AttributeError:
        # Handles cases where request.user might not exist
        return portfolio_context


def is_widescreen_centered(request):
    include_paths = [
        "/domains/",
        "/requests/",
        "/members/",
    ]
    exclude_paths = [
        "/domains/edit",
        "members/new-member/",
    ]

    is_excluded = any(exclude_path in request.path for exclude_path in exclude_paths)

    # Check if the current path matches a path in included_paths or the root path.
    is_widescreen_centered = any(path in request.path for path in include_paths) or request.path == "/"

    # Return a dictionary with the widescreen mode status.
    return {"is_widescreen_centered": is_widescreen_centered and not is_excluded}
