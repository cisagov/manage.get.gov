from django.http import JsonResponse
from django.core.paginator import Paginator
from registrar.models import UserDomainRole, Domain

def get_domains_json(request):
    """Given the current request,
    get all domains that are associated with the UserDomainRole object"""

    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)

    user_domain_roles = UserDomainRole.objects.filter(user=request.user)
    domain_ids = user_domain_roles.values_list("domain_id", flat=True)

    objects = Domain.objects.filter(id__in=domain_ids)

    # Handle sorting
    sort_by = request.GET.get('sort_by', 'id')  # Default to 'id'
    order = request.GET.get('order', 'asc')  # Default to 'asc'

    if order == 'desc':
        sort_by = f'-{sort_by}'

    objects = objects.order_by(sort_by)

    paginator = Paginator(objects, 2)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    domains = list(page_obj.object_list.values())  # Convert QuerySet to list of dicts

    return JsonResponse({
        'domains': domains,
        'page': page_obj.number,
        'num_pages': paginator.num_pages,
        'has_previous': page_obj.has_previous(),
        'has_next': page_obj.has_next(),
    })