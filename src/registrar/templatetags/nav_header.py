"""Loads user portfolio data to display on Organizations nav dropdown."""

from django import template
from registrar.models import UserPortfolioPermission

register = template.Library()


@register.inclusion_tag("includes/portfolio_organizations_dropdown.html", takes_context=True)
def portfolio_organizations_dropdown(context):
    user = context["user"]
    # Ignore incomplete MagicMock user created in test_login_callback_does_not_requires_step_up_auth
    if user.__class__.__name__ == "User":
        return {"user_portfolio_permissions": UserPortfolioPermission.objects.filter(user=user).order_by("portfolio")}
