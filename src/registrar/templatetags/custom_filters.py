import logging
from django import template
import re
from registrar.models.domain_request import DomainRequest
from registrar.models.user_domain_role import UserDomainRole
from registrar.models import User
from phonenumber_field.phonenumber import PhoneNumber
from registrar.views.domain_request import DomainRequestWizard

from registrar.models.utility.generic_helper import get_url_name

register = template.Library()
logger = logging.getLogger(__name__)


@register.filter(name="extract_value")
def extract_value(html_input):
    match = re.search(r'value="([^"]*)"', html_input)
    if match:
        return match.group(1)
    return ""


@register.filter
def extract_a_text(value):
    # Use regex to extract the text within the <a> tag
    pattern = r"<a\b[^>]*>(.*?)</a>"
    match = re.search(pattern, value)
    if match:
        # Get the content and strip any nested HTML tags
        content = match.group(1)
        # Remove any nested HTML tags (like <img>)
        text_pattern = r"<[^>]+>"
        text_only = re.sub(text_pattern, "", content)
        # Clean up any extra whitespace
        return text_only.strip()

    return ""


@register.filter
def find_index(haystack, needle):
    try:
        return haystack.index(needle)
    except ValueError:
        return -1


@register.filter
def slice_after(value, substring):
    index = value.find(substring)
    if index != -1:
        result = value[index + len(substring) :]
        return result
    return value


@register.filter
def contains_checkbox(html_list):
    for html_string in html_list:
        if re.search(r'<input[^>]*type="checkbox"', html_string):
            return True
    return False


@register.filter
def get_organization_long_name(generic_org_type):
    organization_choices_dict = dict(DomainRequest.OrganizationChoicesVerbose.choices)
    long_form_type = organization_choices_dict[generic_org_type]
    if long_form_type is None:
        logger.error("Organization type error, triggered by a template's custom filter")
        return "Error"

    return long_form_type


@register.filter(name="has_permission")
def has_permission(user, permission):
    return user.has_perm(permission)


@register.filter
def get_region(state):
    if state and isinstance(state, str):
        regions = {
            "CT": 1,
            "ME": 1,
            "MA": 1,
            "NH": 1,
            "RI": 1,
            "VT": 1,
            "NJ": 2,
            "NY": 2,
            "PR": 2,
            "VI": 2,
            "DE": 3,
            "DC": 3,
            "MD": 3,
            "PA": 3,
            "VA": 3,
            "WV": 3,
            "AL": 4,
            "FL": 4,
            "GA": 4,
            "KY": 4,
            "MS": 4,
            "NC": 4,
            "SC": 4,
            "TN": 4,
            "IL": 5,
            "IN": 5,
            "MI": 5,
            "MN": 5,
            "OH": 5,
            "WI": 5,
            "AR": 6,
            "LA": 6,
            "NM": 6,
            "OK": 6,
            "TX": 6,
            "IA": 7,
            "KS": 7,
            "MO": 7,
            "NE": 7,
            "CO": 8,
            "MT": 8,
            "ND": 8,
            "SD": 8,
            "UT": 8,
            "WY": 8,
            "AZ": 9,
            "CA": 9,
            "HI": 9,
            "NV": 9,
            "GU": 9,
            "AS": 9,
            "MP": 9,
            "AK": 10,
            "ID": 10,
            "OR": 10,
            "WA": 10,
        }
        return regions.get(state.upper(), "N/A")
    else:
        return None


@register.filter
def format_phone(value):
    """Converts a phonenumber to a national format"""
    if value:
        phone_number = value
        if isinstance(value, str):
            phone_number = PhoneNumber.from_string(value)
        return phone_number.as_national
    return value


@register.filter
def in_path(url, path):
    return url in path


@register.filter(name="and")
def and_filter(value, arg):
    """
    Implements logical AND operation in templates.
    Usage: {{ value|and:arg }}
    """
    return bool(value and arg)


@register.filter(name="has_contact_info")
def has_contact_info(user):
    """Checks if the given object has the attributes: title, email, phone
    and checks if at least one of those is not null."""
    if not hasattr(user, "title") or not hasattr(user, "email") or not hasattr(user, "phone"):
        return False
    else:
        return bool(user.title or user.email or user.phone)


@register.filter
def model_name_lowercase(instance):
    return instance.__class__.__name__.lower()


@register.filter(name="is_domain_subpage")
def is_domain_subpage(path):
    """Checks if the given page is a subpage of domains.
    Takes a path name, like '/domains/'."""
    # Since our pages aren't unified under a common path, we need this approach for now.
    url_names = [
        "domains",
        "no-portfolio-domains",
        "domain",
        "domain-users",
        "domain-dns",
        "domain-dns-nameservers",
        "domain-dns-dnssec",
        "domain-dns-dnssec-dsdata",
        "domain-your-contact-information",
        "domain-org-name-address",
        "domain-senior-official",
        "domain-security-email",
        "domain-suborganization",
        "domain-users-add",
        "domain-request-delete",
        "domain-user-delete",
        "domain-renewal",
        "invitation-cancel",
        "domain-delete",
        "domain-lifecycle",
    ]
    return get_url_name(path) in url_names


@register.filter(name="is_domain_request_subpage")
def is_domain_request_subpage(path):
    """Checks if the given page is a subpage of domain requests.
    Takes a path name, like '/requests/'."""
    # Since our pages aren't unified under a common path, we need this approach for now.
    url_names = [
        "domain-requests",
        "no-portfolio-requests",
        "domain-request-status",
        "domain-request-withdraw-confirmation",
        "domain-request-withdrawn",
        "domain-request-delete",
        "domain-request",
        "portfolio_requesting_entity",
        "dotgov_domain",
        "purpose",
        "portfolio_additional_details",
        "requirements",
        "review",
    ]

    # The domain request wizard pages don't have a defined path,
    # so we need to check directly on it.
    wizard_paths = [
        DomainRequestWizard.EDIT_URL_NAME,
        DomainRequestWizard.URL_NAMESPACE,
        DomainRequestWizard.NEW_URL_NAME,
    ]
    return get_url_name(path) in url_names or any(wizard in path for wizard in wizard_paths)


@register.filter(name="is_portfolio_subpage")
def is_portfolio_subpage(path):
    """Checks if the given page is a subpage of portfolio.
    Takes a path name, like '/organization/'."""
    # Since our pages aren't unified under a common path, we need this approach for now.
    url_names = [
        "organization",
        "organization-info",
        "organization-senior-official",
    ]
    return get_url_name(path) in url_names


@register.filter(name="is_members_subpage")
def is_members_subpage(path):
    """Checks if the given page is a subpage of members.
    Takes a path name, like '/organization/'."""
    # Since our pages aren't unified under a common path, we need this approach for now.
    url_names = [
        "members",
        "member",
        "member-permissions",
        "invitedmember",
        "invitedmember-permissions",
        "member-domains",
    ]
    return get_url_name(path) in url_names


@register.filter(name="display_requesting_entity")
def display_requesting_entity(domain_request):
    """Workaround for a newline issue in .txt files (our emails) as if statements
    count as a newline to the file.
    Will output something that looks like:
    MyOrganizationName
    Boise, ID
    """
    display = ""
    if domain_request.sub_organization:
        display = domain_request.sub_organization
    elif domain_request.requesting_entity_is_suborganization():
        display = (
            f"{domain_request.requested_suborganization}\n"
            f"{domain_request.suborganization_city}, {domain_request.suborganization_state_territory}"
        )
    elif domain_request.requesting_entity_is_portfolio():
        display = (
            f"{domain_request.portfolio.organization_name}\n"
            f"{domain_request.portfolio.city}, {domain_request.portfolio.state_territory}"
        )

    return display


@register.filter
def get_dict_value(dictionary, key):
    """Get a value from a dictionary. Returns a string on empty."""
    if isinstance(dictionary, dict):
        return dictionary.get(key, "")
    return ""


@register.filter
def button_class(custom_class):
    default_class = "usa-button"
    return f"{default_class} {custom_class}" if custom_class else default_class


@register.simple_tag(takes_context=True)
def get_user_nav_modes(context):
    request = context.get("request")
    user = getattr(request, "user", None)

    modes = dict(is_enterprise=False, is_legacy=False, is_both=False)

    if not user or not hasattr(user, "is_authenticated") or not user.is_authenticated:
        return modes
    
    try:
        is_enterprise = user.is_org_user(request) or user.is_any_org_user()

        has_legacy_domains = UserDomainRole.objects.filter(user=user).exists()
        has_legacy_requests = DomainRequest.objects.filter(requester=user).exists()
        is_grandfathered = user.verification_type == User.VerificationTypeChoices.GRANDFATHERED
        has_perm = user.has_perm("registrar.analyst_access_permission") or user.has_perm("registrar.full_access_permission")

        is_legacy = has_legacy_domains or has_legacy_requests or is_grandfathered or has_perm

        modes["is_enterprise"] = is_enterprise
        modes["is_legacydocker compose run app python manage.py test --parallel" \
        ""] = is_legacy
        modes["is_both"] = is_enterprise and is_legacy
    except (AttributeError, TypeError, ValueError):
        logger.warning("Error in get_user_nav_modes for user %s", user, exc_info=True)

    return modes


@register.simple_tag(takes_context=True)
def get_user_portfolios(context):
    request = context.get("request")

    user = getattr(request, "user", None)

    if not user or not hasattr(user, "is_authenticated") or not user.is_authenticated:
        return []
    
    try:
        perms = user.get_portfolios().select_related("portfolio")
        portfolios = [pp.portfolio for pp in perms if getattr(pp, "portfolio", None)]

        return sorted(portfolios, key=lambda p: p.organization_name or "")
    except (AttributeError, TypeError, ValueError):
        logger.warninig("Error in get_user_portolios for user %s", user, exc_info=True)
