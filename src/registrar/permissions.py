"""
Centralized permissions management for the registrar.
"""

from django.urls import URLResolver, get_resolver, URLPattern
from registrar.decorators import (
    HAS_DOMAIN_REQUESTS_VIEW_ALL,
    HAS_PORTFOLIO_DOMAIN_REQUESTS_ANY_PERM,
    IS_STAFF,
    IS_DOMAIN_MANAGER,
    IS_DOMAIN_MANAGER_AND_NOT_PORTFOLIO_MEMBER,
    IS_PORTFOLIO_MEMBER_AND_DOMAIN_MANAGER,
    IS_CISA_ANALYST,
    IS_OMB_ANALYST,
    IS_FULL_ACCESS,
    IS_DOMAIN_REQUEST_REQUESTER,
    IS_STAFF_MANAGING_DOMAIN,
    IS_PORTFOLIO_MEMBER,
    IS_MULTIPLE_PORTFOLIOS_MEMBER,
    HAS_LEGACY_AND_ORG_USER,
    HAS_PORTFOLIO_DOMAINS_ANY_PERM,
    HAS_PORTFOLIO_DOMAINS_VIEW_ALL,
    HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT,
    HAS_PORTFOLIO_MEMBERS_EDIT,
    HAS_PORTFOLIO_MEMBERS_ANY_PERM,
    HAS_PORTFOLIO_MEMBERS_VIEW,
    ALL,
)

# Define permissions for each URL pattern by name
URL_PERMISSIONS = {
    # Home & general pages
    "home": [ALL],
    "health": [ALL],  # Intentionally no decorator
    # Domain management
    "domain": [HAS_PORTFOLIO_DOMAINS_VIEW_ALL, IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN],
    "domain-dns": [IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN],
    "domain-dns-nameservers": [IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN],
    "domain-dns-dnssec": [IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN],
    "domain-dns-dnssec-dsdata": [IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN],
    "domain-org-name-address": [IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN],
    "domain-suborganization": [IS_PORTFOLIO_MEMBER_AND_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN],
    "domain-senior-official": [IS_DOMAIN_MANAGER_AND_NOT_PORTFOLIO_MEMBER, IS_STAFF_MANAGING_DOMAIN],
    "domain-security-email": [IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN],
    "domain-renewal": [IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN],
    "domain-users": [IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN],
    "domain-users-add": [IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN],
    "domain-user-delete": [IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN],
    # Portfolio management
    "domains": [HAS_PORTFOLIO_DOMAINS_ANY_PERM],
    "no-portfolio-domains": [IS_PORTFOLIO_MEMBER],
    "no-organization-domains": [IS_PORTFOLIO_MEMBER],
    "members": [HAS_PORTFOLIO_MEMBERS_ANY_PERM],
    "member": [HAS_PORTFOLIO_MEMBERS_ANY_PERM],
    "member-delete": [HAS_PORTFOLIO_MEMBERS_EDIT],
    "member-permissions": [HAS_PORTFOLIO_MEMBERS_EDIT],
    "member-domains": [HAS_PORTFOLIO_MEMBERS_ANY_PERM],
    "member-domains-edit": [HAS_PORTFOLIO_MEMBERS_EDIT],
    "invitedmember": [HAS_PORTFOLIO_MEMBERS_ANY_PERM],
    "invitedmember-delete": [HAS_PORTFOLIO_MEMBERS_EDIT],
    "invitedmember-permissions": [HAS_PORTFOLIO_MEMBERS_EDIT],
    "invitedmember-domains": [HAS_PORTFOLIO_MEMBERS_ANY_PERM],
    "invitedmember-domains-edit": [HAS_PORTFOLIO_MEMBERS_EDIT],
    "new-member": [HAS_PORTFOLIO_MEMBERS_EDIT],
    "domain-requests": [HAS_PORTFOLIO_DOMAIN_REQUESTS_ANY_PERM],
    "no-portfolio-requests": [IS_PORTFOLIO_MEMBER],
    "organization": [IS_PORTFOLIO_MEMBER],
    "organization-info": [IS_PORTFOLIO_MEMBER],
    "organization-senior-official": [IS_PORTFOLIO_MEMBER],
    "your-organizations": [IS_MULTIPLE_PORTFOLIOS_MEMBER, HAS_LEGACY_AND_ORG_USER],
    "set-session-portfolio": [IS_MULTIPLE_PORTFOLIOS_MEMBER, HAS_LEGACY_AND_ORG_USER],
    # Domain requests
    "domain-request-status": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    "domain-request-status-viewonly": [HAS_DOMAIN_REQUESTS_VIEW_ALL],
    "domain-request-withdraw-confirmation": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    "domain-request-withdrawn": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    "domain-request-delete": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    "edit-domain-request": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    # Admin functions
    "analytics": [IS_CISA_ANALYST, IS_FULL_ACCESS],
    "export_data_type": [IS_CISA_ANALYST, IS_FULL_ACCESS],
    "export_data_full": [IS_CISA_ANALYST, IS_FULL_ACCESS],
    "export_data_domain_requests_full": [IS_CISA_ANALYST, IS_FULL_ACCESS],
    "export_data_federal": [IS_CISA_ANALYST, IS_FULL_ACCESS],
    "export_domains_growth": [IS_CISA_ANALYST, IS_FULL_ACCESS],
    "export_requests_growth": [IS_CISA_ANALYST, IS_FULL_ACCESS],
    "export_managed_domains": [IS_CISA_ANALYST, IS_FULL_ACCESS],
    "export_unmanaged_domains": [IS_CISA_ANALYST, IS_FULL_ACCESS],
    "transfer_user": [IS_CISA_ANALYST, IS_FULL_ACCESS],
    # Analytics
    "all-domain-metadata": [IS_STAFF],
    "current-full": [IS_STAFF],
    "all-domain-requests-metadata": [IS_STAFF],
    "domain-growth": [IS_STAFF],
    "request-growth": [IS_STAFF],
    "managed-domains": [IS_STAFF],
    "unmanaged-domains": [IS_STAFF],
    # Reports
    "export-user-domains-as-csv": [IS_STAFF],
    "export-portfolio-members-as-csv": [IS_STAFF],
    "export_members_portfolio": [HAS_PORTFOLIO_MEMBERS_VIEW],
    "export_data_type_user": [ALL],
    # API endpoints
    "get-senior-official-from-federal-agency-json": [IS_CISA_ANALYST, IS_FULL_ACCESS, IS_OMB_ANALYST],
    "get-portfolio-json": [IS_CISA_ANALYST, IS_FULL_ACCESS, IS_OMB_ANALYST],
    "get-suborganization-list-json": [IS_CISA_ANALYST, IS_FULL_ACCESS, IS_OMB_ANALYST],
    "get-federal-and-portfolio-types-from-federal-agency-json": [IS_CISA_ANALYST, IS_FULL_ACCESS, IS_OMB_ANALYST],
    "get-action-needed-email-for-user-json": [IS_CISA_ANALYST, IS_FULL_ACCESS, IS_OMB_ANALYST],
    "get-rejection-email-for-user-json": [IS_CISA_ANALYST, IS_FULL_ACCESS, IS_OMB_ANALYST],
    "get_domains_json": [ALL],
    "get_domain_requests_json": [ALL],
    "get_portfolio_members_json": [HAS_PORTFOLIO_MEMBERS_ANY_PERM],
    "get_member_domains_json": [HAS_PORTFOLIO_MEMBERS_ANY_PERM],
    # User profile
    "finish-user-profile-setup": [ALL],
    "user-profile": [ALL],
    # Invitation
    "invitation-cancel": [IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN],
    # DNS Hosting
    "domain-dns-records": [IS_STAFF],
    # Domain request wizard
    "start": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    "finished": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    "generic_org_type": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    "tribal_government": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    "organization_federal": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    "organization_election": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    "organization_contact": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    "about_your_organization": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    "senior_official": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    "current_sites": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    "dotgov_domain": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    "purpose": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    "other_contacts": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    "additional_details": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    "requirements": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    "review": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    "portfolio_requesting_entity": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    "portfolio_additional_details": [HAS_PORTFOLIO_DOMAIN_REQUESTS_EDIT, IS_DOMAIN_REQUEST_REQUESTER],
    "domain-delete": [IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN],
    "domain-lifecycle": [IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN],
    "version": [ALL],
}

UNCHECKED_URLS = [
    "health",
    "openid/",
    "get-current-federal",
    "get-current-full",
    "available",
    "rdap",
    "todo",
    "logout",
    "version",
]


def verify_all_urls_have_permissions():
    """
    Utility function to verify that all URLs in the application have defined permissions
    in the permissions mapping.
    """

    resolver = get_resolver()
    missing_permissions = []
    missing_names = []

    # Collect all URL pattern names
    for pattern in resolver.url_patterns:
        # Skip URLResolver objects (like admin.site.urls)
        if isinstance(pattern, URLResolver):
            continue

        if hasattr(pattern, "name") and pattern.name:
            if pattern.name not in URL_PERMISSIONS and pattern.name not in UNCHECKED_URLS:
                missing_permissions.append(pattern.name)
        else:
            raise ValueError(f"URL pattern {pattern} has no name")

    if missing_names:
        raise ValueError(f"The following URL patterns have no name: {missing_names}")

    return missing_permissions


def validate_permissions():  # noqa: C901
    """
    Validates that all URL patterns have consistent permission rules between
    the centralized mapping and view decorators.

    Returns a dictionary of issues found.
    """

    resolver = get_resolver()
    issues = {
        "missing_in_mapping": [],  # URLs with decorators but not in mapping
        "missing_decorator": [],  # URLs in mapping but missing decorators
        "permission_mismatch": [],  # URLs with different permissions
    }

    def check_url_pattern(pattern, parent_path=""):
        if isinstance(pattern, URLPattern):
            view_func = pattern.callback
            path = f"{parent_path}/{pattern.pattern}"
            url_name = pattern.name

            if url_name:
                # Skip check for endpoints that intentionally have no decorator
                if url_name in UNCHECKED_URLS:
                    return

                # Check if view has decorator but missing from mapping
                if getattr(view_func, "has_explicit_access", False) and url_name not in URL_PERMISSIONS:
                    issues["missing_in_mapping"].append((url_name, path))

                # Check if view is in mapping but missing decorator
                elif url_name in URL_PERMISSIONS and not getattr(view_func, "has_explicit_access", False):
                    issues["missing_decorator"].append((url_name, path))

                # Check if permissions match (more complex, may need refinement)
                elif getattr(view_func, "has_explicit_access", False) and url_name in URL_PERMISSIONS:
                    view_permissions = getattr(view_func, "_access_rules", set())
                    mapping_permissions = set(URL_PERMISSIONS[url_name])

                    if view_permissions != mapping_permissions:
                        issues["permission_mismatch"].append((url_name, path, view_permissions, mapping_permissions))

        elif isinstance(pattern, URLResolver):
            # Handle included URL patterns (nested)
            new_parent = f"{parent_path}/{pattern.pattern}"
            for p in pattern.url_patterns:
                check_url_pattern(p, new_parent)

    # Check all URL patterns
    for pattern in resolver.url_patterns:
        check_url_pattern(pattern)

    return issues
