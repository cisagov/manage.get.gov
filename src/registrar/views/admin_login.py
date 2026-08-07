from django.contrib import admin
from registrar.decorators import grant_access, ALL


@grant_access(ALL)
def admin_login(request):
    """Shadows Django admin's login URL so LoginRequiredMiddleware redirects
    unauthenticated users to Login.gov. Authenticated users get Django's normal
    admin login behavior: staff go to the admin index; non-staff see the
    "You are authenticated as <user id>" page."""
    return admin.site.login(request)
