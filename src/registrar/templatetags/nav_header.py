"""Loads user portfolio data to display on Organizations nav dropdown."""

from django import template
from registrar.models import UserPortfolioPermission

register = template.Library()


@register.inclusion_tag("includes/portfolio_organizations_dropdown.html", takes_context=True)
def portfolio_organizations_dropdown(context):
    user = context["user"]
    return {"user_portfolio_permissions": UserPortfolioPermission.objects.filter(user=user).order_by("portfolio")}

