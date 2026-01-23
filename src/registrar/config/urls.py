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
    ExportMembersPortfolio,
)

# --jsons
from registrar.views.domain_requests_json import get_domain_requests_json
from registrar.views.domains_json import get_domains_json
from registrar.views.utility.api_views import (
    get_senior_official_from_federal_agency_json,
    get_portfolio_json,
    get_suborganization_list_json,
    get_federal_and_portfolio_types_from_federal_agency_json,
    get_action_needed_email_for_user_json,
    get_rejection_email_for_user_json,
    get_alert_messages
)

from registrar.views.domain_request import Step, PortfolioDomainRequestStep
from registrar.views.transfer_user import TransferUserView
from registrar.views.utility import always_404
from api.views import available, rdap, get_current_federal, get_current_full

DOMAIN_REQUEST_NAMESPACE = views.DomainRequestWizard.URL_NAMESPACE

# dynamically generate the other domain_request_urls
domain_request_urls = [
    path("", RedirectView.as_view(pattern_name="domain-request:start"), name="redirect-to-start"),
    path("start/", views.DomainRequestWizard.as_view(), name=views.DomainRequestWizard.NEW_URL_NAME),
    path("finished/", views.Finished.as_view(), name=views.DomainRequestWizard.FINISHED_URL_NAME),
]
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
    (Step.OTHER_CONTACTS, views.OtherContacts),
    (Step.ADDITIONAL_DETAILS, views.AdditionalDetails),
    (Step.REQUIREMENTS, views.Requirements),
    (Step.REVIEW, views.Review),
    # Portfolio steps
    (PortfolioDomainRequestStep.REQUESTING_ENTITY, views.RequestingEntity),
    (PortfolioDomainRequestStep.ADDITIONAL_DETAILS, views.PortfolioAdditionalDetails),
]:
    domain_request_urls.append(path(f"<int:domain_request_pk>/{step}/", view.as_view(), name=step))


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
        "members/",
        views.PortfolioMembersView.as_view(),
        name="members",
    ),
    path(
        "member/<int:member_pk>",
        views.PortfolioMemberView.as_view(),
        name="member",
    ),
    path(
        "member/<int:member_pk>/delete",
        views.PortfolioMemberDeleteView.as_view(),
        name="member-delete",
    ),
    path(
        "member/<int:member_pk>/permissions",
        views.PortfolioMemberEditView.as_view(),
        name="member-permissions",
    ),
    path(
        "member/<int:member_pk>/domains",
        views.PortfolioMemberDomainsView.as_view(),
        name="member-domains",
    ),
    path(
        "member/<int:member_pk>/domains/edit",
        views.PortfolioMemberDomainsEditView.as_view(),
        name="member-domains-edit",
    ),
    path(
        "invitedmember/<int:invitedmember_pk>",
        views.PortfolioInvitedMemberView.as_view(),
        name="invitedmember",
    ),
    path(
        "invitedmember/<int:invitedmember_pk>/delete",
        views.PortfolioInvitedMemberDeleteView.as_view(),
        name="invitedmember-delete",
    ),
    path(
        "invitedmember/<int:invitedmember_pk>/permissions",
        views.PortfolioInvitedMemberEditView.as_view(),
        name="invitedmember-permissions",
    ),
    path(
        "invitedmember/<int:invitedmember_pk>/domains",
        views.PortfolioInvitedMemberDomainsView.as_view(),
        name="invitedmember-domains",
    ),
    path(
        "invitedmember/<int:invitedmember_pk>/domains/edit",
        views.PortfolioInvitedMemberDomainsEditView.as_view(),
        name="invitedmember-domains-edit",
    ),
    # path(
    #     "no-organization-members/",
    #     views.PortfolioNoMembersView.as_view(),
    #     name="no-portfolio-members",
    # ),
    path(
        "members/new-member/",
        views.PortfolioAddMemberView.as_view(),
        name="new-member",
    ),
    path(
        "requests/",
        views.PortfolioDomainRequestsView.as_view(),
        name="domain-requests",
    ),
    path(
        "no-organization-requests/",
        views.PortfolioNoDomainRequestsView.as_view(),
        name="no-portfolio-requests",
    ),
    path(
        "organization/",
        views.PortfolioOrganizationView.as_view(),
        name="organization",
    ),
    path(
        "organization/organization-info",
        views.PortfolioOrganizationInfoView.as_view(),
        name="organization-info",
    ),
    path(
        "organization/senior-official",
        views.PortfolioSeniorOfficialView.as_view(),
        name="organization-senior-official",
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
    path("admin/registrar/user/<int:user_id>/transfer/", TransferUserView.as_view(), name="transfer_user"),
    path(
        "admin/api/get-senior-official-from-federal-agency-json/",
        get_senior_official_from_federal_agency_json,
        name="get-senior-official-from-federal-agency-json",
    ),
    path(
        "admin/api/get-portfolio-json/",
        get_portfolio_json,
        name="get-portfolio-json",
    ),
    path(
        "admin/api/get-suborganization-list-json/",
        get_suborganization_list_json,
        name="get-suborganization-list-json",
    ),
    path(
        "admin/api/get-federal-and-portfolio-types-from-federal-agency-json/",
        get_federal_and_portfolio_types_from_federal_agency_json,
        name="get-federal-and-portfolio-types-from-federal-agency-json",
    ),
    path(
        "admin/api/get-action-needed-email-for-user-json/",
        get_action_needed_email_for_user_json,
        name="get-action-needed-email-for-user-json",
    ),
    path(
        "admin/api/get-rejection-email-for-user-json/",
        get_rejection_email_for_user_json,
        name="get-rejection-email-for-user-json",
    ),
    path("admin/", admin.site.urls),
    path(
        "reports/export_members_portfolio/",
        ExportMembersPortfolio.as_view(),
        name="export_members_portfolio",
    ),
    path(
        "reports/export_data_type_user/",
        ExportDataTypeUser.as_view(),
        name="export_data_type_user",
    ),
    path(
        "domain-request/<int:domain_request_pk>/edit/",
        views.DomainRequestWizard.as_view(),
        name=views.DomainRequestWizard.EDIT_URL_NAME,
    ),
    path(
        "domain-request/<int:domain_request_pk>",
        views.DomainRequestStatus.as_view(),
        name="domain-request-status",
    ),
    path(
        "domain-request/viewonly/<int:domain_request_pk>",
        views.DomainRequestStatusViewOnly.as_view(),
        name="domain-request-status-viewonly",
    ),
    path(
        "domain-request/<int:domain_request_pk>/withdraw",
        views.DomainRequestWithdrawConfirmation.as_view(),
        name="domain-request-withdraw-confirmation",
    ),
    path(
        "domain-request/<int:domain_request_pk>/withdrawconfirmed",
        views.DomainRequestWithdrawn.as_view(),
        name="domain-request-withdrawn",
    ),
    path("health", views.health, name="health"),
    path("openid/", include("djangooidc.urls")),
    path("request/", include((domain_request_urls, DOMAIN_REQUEST_NAMESPACE))),
    path("api/v1/available/", available, name="available"),
    path("api/v1/rdap/", rdap, name="rdap"),
    path("api/v1/get-report/current-federal", get_current_federal, name="get-current-federal"),
    path("api/v1/get-report/current-full", get_current_full, name="get-current-full"),
    path(
        "todo",
        lambda r: always_404(r, "We forgot to include this link, sorry."),
        name="todo",
    ),
    path("domain/<int:domain_pk>", views.DomainView.as_view(), name="domain"),
    path(
        "domain/<int:domain_pk>/dns/records",
        views.DomainDNSRecordsView.as_view(),
        name="domain-dns-records",
    ),
    path(
        "domain/<int:domain_pk>/dns/create-record",
        views.DomainDNSRecordFormView.as_view(),
        name="domain-dns-create-record"
    ),
    path("domain/<int:domain_pk>/users", views.DomainUsersView.as_view(), name="domain-users"),
    path(
        "domain/<int:domain_pk>/dns",
        views.DomainDNSView.as_view(),
        name="domain-dns",
    ),
    path(
        "domain/<int:domain_pk>/dns/nameservers",
        views.DomainNameserversView.as_view(),
        name="domain-dns-nameservers",
    ),
    path(
        "domain/<int:domain_pk>/dns/dnssec",
        views.DomainDNSSECView.as_view(),
        name="domain-dns-dnssec",
    ),
    path(
        "domain/<int:domain_pk>/dns/dnssec/dsdata",
        views.DomainDsDataView.as_view(),
        name="domain-dns-dnssec-dsdata",
    ),
    path(
        "domain/<int:domain_pk>/org-name-address",
        views.DomainOrgNameAddressView.as_view(),
        name="domain-org-name-address",
    ),
    path(
        "domain/<int:domain_pk>/suborganization",
        views.DomainSubOrganizationView.as_view(),
        name="domain-suborganization",
    ),
    path(
        "domain/<int:domain_pk>/senior-official",
        views.DomainSeniorOfficialView.as_view(),
        name="domain-senior-official",
    ),
    path(
        "domain/<int:domain_pk>/security-email",
        views.DomainSecurityEmailView.as_view(),
        name="domain-security-email",
    ),
    path(
        "domain/<int:domain_pk>/domain-lifecycle",
        views.DomainLifecycleView.as_view(),
        name="domain-lifecycle",
    ),
    path(
        "domain/<int:domain_pk>/renewal",
        views.DomainRenewalView.as_view(),
        name="domain-renewal",
    ),
    path(
        "domain/<int:domain_pk>/users/add",
        views.DomainAddUserView.as_view(),
        name="domain-users-add",
    ),
    path(
        "domain/<int:domain_pk>/delete",
        views.DomainDeleteView.as_view(),
        name="domain-delete",
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
        "invitation/<int:domain_invitation_pk>/cancel",
        views.DomainInvitationCancelView.as_view(http_method_names=["post"]),
        name="invitation-cancel",
    ),
    path(
        "domain-request/<int:domain_request_pk>/delete",
        views.DomainRequestDeleteView.as_view(http_method_names=["post"]),
        name="domain-request-delete",
    ),
    path(
        "domain/<int:domain_pk>/users/<int:user_pk>/delete",
        views.DomainDeleteUserView.as_view(http_method_names=["post"]),
        name="domain-user-delete",
    ),
    path("get-domains-json/", get_domains_json, name="get_domains_json"),
    path("get-domain-requests-json/", get_domain_requests_json, name="get_domain_requests_json"),
    path("get-portfolio-members-json/", views.PortfolioMembersJson.as_view(), name="get_portfolio_members_json"),
    path("get-member-domains-json/", views.PortfolioMemberDomainsJson.as_view(), name="get_member_domains_json"),
    path("your-organizations/", views.PortfolioOrganizationsView.as_view(), name="your-organizations"),
    path(
        "set-session-portfolio/",
        views.PortfolioOrganizationSelectView.as_view(),
        name="set-session-portfolio",
    ),
    path(
        "messages/",
        get_alert_messages,
        name="get-messages"
    )
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
handler404 = "registrar.views.utility.error_views.custom_404_error_view"

# we normally would guard these with `if settings.DEBUG` but tests run with
# DEBUG = False even when these apps have been loaded because settings.DEBUG
# was actually True. Instead, let's add these URLs any time we are able to
# import the debug toolbar package.
try:
    import debug_toolbar  # type: ignore

    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
except ImportError:
    pass
