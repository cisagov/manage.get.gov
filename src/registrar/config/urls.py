"""URL Configuration

For more information see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from registrar.views import health, index, profile

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", index.index),
    path("health/", health.health),
    path("edit_profile/", profile.edit_profile, name="edit-profile"),
    # these views respect the DEBUG setting
    path("__debug__/", include("debug_toolbar.urls")),
]
