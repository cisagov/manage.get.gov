"""URL Configuration

For more information see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from registrar import views
from registrar.views.report_views import (
    ExportDataDomainsGrowth,
    ExportDataFederal,
    ExportDataFull,
    ExportDataManagedDomains,
    ExportDataRequestsGrowth,
    ExportDataType,
    ExportDataUnmanagedDomains,
    AnalyticsView,
    ExportDomainRequestDataFull,
    ExportDataTypeUser,
)

from registrar.views.domain_request import Step
from registrar.views.domain_requests_json import get_domain_requests_json
from registrar.views.utility.api_views import (
    get_senior_official_from_federal_agency_json,
    get_federal_and_portfolio_types_from_federal_agency_json,
)
from registrar.views.domains_json import get_domains_json
from registrar.views.utility import always_404
from api.views import available, get_current_federal, get_current_full


DOMAIN_REQUEST_NAMESPACE = views.DomainRequestWizard.URL_NAMESPACE
domain_request_urls = [
    path("", views.DomainRequestWizard.as_view(), name=""),
    path("finished/", views.Finished.as_view(), name="finished"),
]

# dynamically generate the other domain_request_urls
for step, view in [
    # add/remove steps here
    (Step.ORGANIZATION_TYPE, views.OrganizationType),
    (Step.TRIBAL_GOVERNMENT, views.TribalGovernment),
    (Step.ORGANIZATION_FEDERAL, views.OrganizationFederal),
    (Step.ORGANIZATION_ELECTION, views.OrganizationElection),
    (Step.ORGANIZATION_CONTACT, views.OrganizationContact),
    (Step.ABOUT_YOUR_ORGANIZATION, views.AboutYourOrganization),
    (Step.SENIOR_OFFICIAL, views.SeniorOfficial),
    (Step.CURRENT_SITES, views.CurrentSites),
    (Step.DOTGOV_DOMAIN, views.DotgovDomain),
    (Step.PURPOSE, views.Purpose),
    (Step.YOUR_CONTACT, views.YourContact),
    (Step.OTHER_CONTACTS, views.OtherContacts),
    (Step.ADDITIONAL_DETAILS, views.AdditionalDetails),
    (Step.REQUIREMENTS, views.Requirements),
    (Step.REVIEW, views.Review),
]:
    domain_request_urls.append(path(f"{step}/", view.as_view(), name=step))


urlpatterns = [
    path("", views.index, name="home"),
    path(
        "domains/",
        views.PortfolioDomainsView.as_view(),
        name="domains",
    ),
    path(
        "no-organization-domains/",
        views.PortfolioNoDomainsView.as_view(),
        name="no-portfolio-domains",
    ),
    path(
        "requests/",
        views.PortfolioDomainRequestsView.as_view(),
        name="domain-requests",
    ),
    path(
        "organization/",
        views.PortfolioOrganizationView.as_view(),
        name="organization",
    ),
    path(
        "senior-official/",
        views.PortfolioSeniorOfficialView.as_view(),
        name="senior-official",
    ),
    path(
        "admin/logout/",
        RedirectView.as_view(pattern_name="logout", permanent=False),
    ),
    path(
        "admin/analytics/export_data_type/",
        ExportDataType.as_view(),
        name="export_data_type",
    ),
    path(
        "admin/analytics/export_data_domain_requests_full/",
        ExportDomainRequestDataFull.as_view(),
        name="export_data_domain_requests_full",
    ),
    path(
        "admin/analytics/export_data_full/",
        ExportDataFull.as_view(),
        name="export_data_full",
    ),
    path(
        "admin/analytics/export_data_federal/",
        ExportDataFederal.as_view(),
        name="export_data_federal",
    ),
    path(
        "admin/analytics/export_domains_growth/",
        ExportDataDomainsGrowth.as_view(),
        name="export_domains_growth",
    ),
    path(
        "admin/analytics/export_requests_growth/",
        ExportDataRequestsGrowth.as_view(),
        name="export_requests_growth",
    ),
    path(
        "admin/analytics/export_managed_domains/",
        ExportDataManagedDomains.as_view(),
        name="export_managed_domains",
    ),
    path(
        "admin/analytics/export_unmanaged_domains/",
        ExportDataUnmanagedDomains.as_view(),
        name="export_unmanaged_domains",
    ),
    path(
        "admin/analytics/",
        AnalyticsView.as_view(),
        name="analytics",
    ),
    path(
        "admin/api/get-senior-official-from-federal-agency-json/",
        get_senior_official_from_federal_agency_json,
        name="get-senior-official-from-federal-agency-json",
    ),
    path(
        "admin/api/get-federal-and-portfolio-types-from-federal-agency-json/",
        get_federal_and_portfolio_types_from_federal_agency_json,
        name="get-federal-and-portfolio-types-from-federal-agency-json",
    ),
    path("admin/", admin.site.urls),
    path(
        "reports/export_data_type_user/",
        ExportDataTypeUser.as_view(),
        name="export_data_type_user",
    ),
    path(
        "domain-request/<id>/edit/",
        views.DomainRequestWizard.as_view(),
        name=views.DomainRequestWizard.EDIT_URL_NAME,
    ),
    path(
        "domain-request/<int:pk>",
        views.DomainRequestStatus.as_view(),
        name="domain-request-status",
    ),
    path(
        "domain-request/<int:pk>/withdraw",
        views.DomainRequestWithdrawConfirmation.as_view(),
        name="domain-request-withdraw-confirmation",
    ),
    path(
        "domain-request/<int:pk>/withdrawconfirmed",
        views.DomainRequestWithdrawn.as_view(),
        name="domain-request-withdrawn",
    ),
    path("health", views.health, name="health"),
    path("openid/", include("djangooidc.urls")),
    path("request/", include((domain_request_urls, DOMAIN_REQUEST_NAMESPACE))),
    path("api/v1/available/", available, name="available"),
    path("api/v1/get-report/current-federal", get_current_federal, name="get-current-federal"),
    path("api/v1/get-report/current-full", get_current_full, name="get-current-full"),
    path(
        "todo",
        lambda r: always_404(r, "We forgot to include this link, sorry."),
        name="todo",
    ),
    path("domain/<int:pk>", views.DomainView.as_view(), name="domain"),
    path("domain/<int:pk>/users", views.DomainUsersView.as_view(), name="domain-users"),
    path(
        "domain/<int:pk>/dns",
        views.DomainDNSView.as_view(),
        name="domain-dns",
    ),
    path(
        "domain/<int:pk>/dns/nameservers",
        views.DomainNameserversView.as_view(),
        name="domain-dns-nameservers",
    ),
    path(
        "domain/<int:pk>/dns/dnssec",
        views.DomainDNSSECView.as_view(),
        name="domain-dns-dnssec",
    ),
    path(
        "domain/<int:pk>/dns/dnssec/dsdata",
        views.DomainDsDataView.as_view(),
        name="domain-dns-dnssec-dsdata",
    ),
    path(
        "domain/<int:pk>/your-contact-information",
        views.DomainYourContactInformationView.as_view(),
        name="domain-your-contact-information",
    ),
    path(
        "domain/<int:pk>/org-name-address",
        views.DomainOrgNameAddressView.as_view(),
        name="domain-org-name-address",
    ),
    path(
        "domain/<int:pk>/suborganization",
        views.DomainSubOrganizationView.as_view(),
        name="domain-suborganization",
    ),
    path(
        "domain/<int:pk>/senior-official",
        views.DomainSeniorOfficialView.as_view(),
        name="domain-senior-official",
    ),
    path(
        "domain/<int:pk>/security-email",
        views.DomainSecurityEmailView.as_view(),
        name="domain-security-email",
    ),
    path(
        "domain/<int:pk>/users/add",
        views.DomainAddUserView.as_view(),
        name="domain-users-add",
    ),
    path(
        "finish-profile-setup",
        views.FinishProfileSetupView.as_view(),
        name="finish-user-profile-setup",
    ),
    path(
        "user-profile",
        views.UserProfileView.as_view(),
        name="user-profile",
    ),
    path(
        "invitation/<int:pk>/delete",
        views.DomainInvitationDeleteView.as_view(http_method_names=["post"]),
        name="invitation-delete",
    ),
    path(
        "domain-request/<int:pk>/delete",
        views.DomainRequestDeleteView.as_view(http_method_names=["post"]),
        name="domain-request-delete",
    ),
    path(
        "domain/<int:pk>/users/<int:user_pk>/delete",
        views.DomainDeleteUserView.as_view(http_method_names=["post"]),
        name="domain-user-delete",
    ),
    path("get-domains-json/", get_domains_json, name="get_domains_json"),
    path("get-domain-requests-json/", get_domain_requests_json, name="get_domain_requests_json"),
]

# Djangooidc strips out context data from that context, so we define a custom error
# view through this method.
# If Djangooidc is left to its own devices and uses reverse directly,
# then both context and session information will be obliterated due to:

# a) Djangooidc being out of scope for context_processors
# b) Potential cyclical import errors restricting what kind of data is passable.

# Rather than dealing with that, we keep everything centralized in one location.
# This way, we can share a view for djangooidc, and other pages as we see fit.
handler500 = "registrar.views.utility.error_views.custom_500_error_view"
handler403 = "registrar.views.utility.error_views.custom_403_error_view"

# we normally would guard these with `if settings.DEBUG` but tests run with
# DEBUG = False even when these apps have been loaded because settings.DEBUG
# was actually True. Instead, let's add these URLs any time we are able to
# import the debug toolbar package.
try:
    import debug_toolbar  # type: ignore

    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
except ImportError:
    pass
