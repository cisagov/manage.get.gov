"""URL Configuration

For more information see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from registrar import views

from registrar.views.admin_views import ExportData


from registrar.views.application import Step
from registrar.views.utility import always_404
from api.views import available, get_current_federal, get_current_full


APPLICATION_NAMESPACE = views.ApplicationWizard.URL_NAMESPACE
application_urls = [
    path("", views.ApplicationWizard.as_view(), name=""),
    path("finished/", views.Finished.as_view(), name="finished"),
]

# dynamically generate the other application_urls
for step, view in [
    # add/remove steps here
    (Step.ORGANIZATION_TYPE, views.OrganizationType),
    (Step.TRIBAL_GOVERNMENT, views.TribalGovernment),
    (Step.ORGANIZATION_FEDERAL, views.OrganizationFederal),
    (Step.ORGANIZATION_ELECTION, views.OrganizationElection),
    (Step.ORGANIZATION_CONTACT, views.OrganizationContact),
    (Step.ABOUT_YOUR_ORGANIZATION, views.AboutYourOrganization),
    (Step.AUTHORIZING_OFFICIAL, views.AuthorizingOfficial),
    (Step.CURRENT_SITES, views.CurrentSites),
    (Step.DOTGOV_DOMAIN, views.DotgovDomain),
    (Step.PURPOSE, views.Purpose),
    (Step.YOUR_CONTACT, views.YourContact),
    (Step.OTHER_CONTACTS, views.OtherContacts),
    (Step.ANYTHING_ELSE, views.AnythingElse),
    (Step.REQUIREMENTS, views.Requirements),
    (Step.REVIEW, views.Review),
]:
    application_urls.append(path(f"{step}/", view.as_view(), name=step))


urlpatterns = [
    path("", views.index, name="home"),
    path(
        "admin/logout/",
        RedirectView.as_view(pattern_name="logout", permanent=False),
    ),
    path("export_data/", ExportData.as_view(), name="admin_export_data"),
    path("admin/", admin.site.urls),
    path(
        "application/<id>/edit/",
        views.ApplicationWizard.as_view(),
        name=views.ApplicationWizard.EDIT_URL_NAME,
    ),
    path(
        "application/<int:pk>",
        views.ApplicationStatus.as_view(),
        name="application-status",
    ),
    path(
        "application/<int:pk>/withdraw",
        views.ApplicationWithdrawConfirmation.as_view(),
        name="application-withdraw-confirmation",
    ),
    path(
        "application/<int:pk>/withdrawconfirmed",
        views.ApplicationWithdrawn.as_view(),
        name="application-withdrawn",
    ),
    path("health", views.health, name="health"),
    path("openid/", include("djangooidc.urls")),
    path("request/", include((application_urls, APPLICATION_NAMESPACE))),
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
        "domain/<int:pk>/authorizing-official",
        views.DomainAuthorizingOfficialView.as_view(),
        name="domain-authorizing-official",
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
        "invitation/<int:pk>/delete",
        views.DomainInvitationDeleteView.as_view(http_method_names=["post"]),
        name="invitation-delete",
    ),
    path(
        "application/<int:pk>/delete",
        views.DomainRequestDeleteView.as_view(http_method_names=["post"]),
        name="application-delete",
    ),
    path(
        "domain/<int:pk>/users/<int:user_pk>/delete",
        views.DomainDeleteUserView.as_view(http_method_names=["post"]),
        name="domain-user-delete",
    ),
]

# we normally would guard these with `if settings.DEBUG` but tests run with
# DEBUG = False even when these apps have been loaded because settings.DEBUG
# was actually True. Instead, let's add these URLs any time we are able to
# import the debug toolbar package.
try:
    import debug_toolbar  # type: ignore

    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
except ImportError:
    pass
