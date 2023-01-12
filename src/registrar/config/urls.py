"""URL Configuration

For more information see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from registrar import views
from registrar.views.application import Step
from registrar.views.utility import always_404
from api.views import available

APPLICATION_NAMESPACE = views.ApplicationWizard.URL_NAMESPACE
application_urls = [
    path("", views.ApplicationWizard.as_view(), name=""),
    path("finished/", views.Finished.as_view(), name="finished"),
]

# dynamically generate the other application_urls
for step, view in [
    # add/remove steps here
    (Step.ORGANIZATION_TYPE, views.OrganizationType),
    (Step.ORGANIZATION_FEDERAL, views.OrganizationFederal),
    (Step.ORGANIZATION_ELECTION, views.OrganizationElection),
    (Step.ORGANIZATION_CONTACT, views.OrganizationContact),
    (Step.TYPE_OF_WORK, views.TypeOfWork),
    (Step.AUTHORIZING_OFFICIAL, views.AuthorizingOfficial),
    (Step.CURRENT_SITES, views.CurrentSites),
    (Step.DOTGOV_DOMAIN, views.DotgovDomain),
    (Step.PURPOSE, views.Purpose),
    (Step.YOUR_CONTACT, views.YourContact),
    (Step.OTHER_CONTACTS, views.OtherContacts),
    (Step.SECURITY_EMAIL, views.SecurityEmail),
    (Step.ANYTHING_ELSE, views.AnythingElse),
    (Step.REQUIREMENTS, views.Requirements),
    (Step.REVIEW, views.Review),
]:
    application_urls.append(path(f"{step}/", view.as_view(), name=step))


urlpatterns = [
    path("", views.index, name="home"),
    path("whoami/", views.whoami, name="whoami"),
    path("admin/", admin.site.urls),
    path(
        "application/<id>/edit/",
        views.ApplicationWizard.as_view(),
        name=views.ApplicationWizard.EDIT_URL_NAME,
    ),
    path("health/", views.health),
    path("edit_profile/", views.edit_profile, name="edit-profile"),
    path("openid/", include("djangooidc.urls")),
    path("register/", include((application_urls, APPLICATION_NAMESPACE))),
    path("api/v1/available/<domain>", available, name="available"),
    path(
        "todo",
        lambda r: always_404(r, "We forgot to include this link, sorry."),
        name="todo",
    ),
]


if not settings.DEBUG:
    urlpatterns += [
        # redirect to login.gov
        path(
            "admin/login/", RedirectView.as_view(pattern_name="login", permanent=False)
        ),
        # redirect to login.gov
        path(
            "admin/logout/",
            RedirectView.as_view(pattern_name="logout", permanent=False),
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
