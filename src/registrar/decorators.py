from functools import wraps
from django.http import JsonResponse
from django.core.exceptions import ObjectDoesNotExist

from registrar.models.domain import Domain
from registrar.models.user_domain_role import UserDomainRole

# Constants for clarity
ALL = "all"
IS_SUPERUSER = "is_superuser"
IS_STAFF = "is_staff"
IS_DOMAIN_MANAGER = "is_domain_manager"

def grant_access(*rules):
    """
    Allows multiple rules in a single decorator call:
    @grant_access(IS_STAFF, IS_SUPERUSER, IS_DOMAIN_MANAGER)
    or multiple stacked decorators:
    @grant_access(IS_SUPERUSER)
    @grant_access(IS_DOMAIN_MANAGER)
    """

    def decorator(view_func):
        view_func.has_explicit_access = True  # Mark as explicitly access-controlled
        existing_rules = getattr(view_func, "_access_rules", set())
        existing_rules.update(rules)  # Support multiple rules in one call
        view_func._access_rules = existing_rules  # Store rules on the function

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user

            # Skip authentication if @login_not_required is applied
            if getattr(view_func, "login_not_required", False):
                return view_func(request, *args, **kwargs)

            # Allow everyone if `ALL` is in rules
            if ALL in view_func._access_rules:
                return view_func(request, *args, **kwargs)
            
            # Ensure user is authenticated
            if not user.is_authenticated:
                return JsonResponse({"error": "Authentication required"}, status=403)

            conditions_met = []

            if IS_STAFF in view_func._access_rules:
                conditions_met.append(user.is_staff)

            if not any(conditions_met) and IS_SUPERUSER in view_func._access_rules:
                conditions_met.append(user.is_superuser)

            if not any(conditions_met) and IS_DOMAIN_MANAGER in view_func._access_rules:
                domain_id = kwargs.get('pk') or kwargs.get('domain_id')
                if not domain_id:
                    return JsonResponse({"error": "Domain ID missing"}, status=400)
                try:
                    domain = Domain.objects.get(pk=domain_id)
                    has_permission = UserDomainRole.objects.filter(
                        user=user, domain=domain
                    ).exists()
                    conditions_met.append(has_permission)
                except ObjectDoesNotExist:
                    return JsonResponse({"error": "Invalid Domain"}, status=404)

            if not any(conditions_met):
                return JsonResponse({"error": "Access Denied"}, status=403)

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator
