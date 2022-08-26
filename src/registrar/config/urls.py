"""URL Configuration

For more information see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from registrar.views import health

urlpatterns = [path("admin/", admin.site.urls), path("health/", health.health)]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
