from django.conf import settings

from registrar.models.user import User


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


def portfolio_permissions(request):
    """Make portfolio permissions for the request user available in global context"""
    try:
        if not request.user or not request.user.is_authenticated:
            return {
                "has_base_portfolio_permission": False,
                "has_domains_portfolio_permission": False,
                "has_domain_requests_portfolio_permission": False,
            }
        return {
            "has_base_portfolio_permission": request.user.has_portfolio_permission(
                User.UserPortfolioPermissionChoices.VIEW_PORTFOLIO
            ),
            "has_domains_portfolio_permission": request.user.has_portfolio_permission(
                User.UserPortfolioPermissionChoices.VIEW_DOMAINS
            ),
            "has_domain_requests_portfolio_permission": request.user.has_portfolio_permission(
                User.UserPortfolioPermissionChoices.VIEW_REQUESTS
            ),
        }
    except AttributeError:
        # Handles cases where request.user might not exist
        return {
            "has_base_portfolio_permission": False,
            "has_domains_portfolio_permission": False,
            "has_domain_requests_portfolio_permission": False,
        }
