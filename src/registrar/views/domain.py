"""View for a single Domain."""

from django.views.generic import DetailView

from registrar.models import Domain

class DomainView(DetailView):

    model = Domain
    template_name = "domain_detail.html"
    context_object_name = "domain"
