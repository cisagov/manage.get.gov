"""Admin-related views."""

from django.http import HttpResponse, JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render

from registrar.utility import csv_export
from ..forms import DataExportForm
from django.views.generic import TemplateView

from registrar.models import (
    Domain,
    DomainApplication,
    DomainInvitation,
    DomainInformation,
    UserDomainRole,
)
import logging


logger = logging.getLogger(__name__)


class ExportData(View):
    
    template_name = "admin/index.html"
    form_class = DataExportForm

    
    def get_context_data(self, **kwargs):
        print('VIE VIE VIE')
        context = super().get_context_data(**kwargs)
        context['form'] = self.form_class()
        context['test'] = 'testing the context'
        return context
    
    def get(self, request, *args, **kwargs):
        # Get start_date and end_date from the request's GET parameters
        start_date = request.GET.get('start_date', '')
        end_date = request.GET.get('end_date', '')
        
        print(start_date)
        print(end_date)
        # Do something with start_date and end_date, e.g., include in the CSV export logic

        # # Federal only
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="growth-from-{start_date}-to-{end_date}.csv"'
        csv_export.export_data_growth_to_csv(response, start_date, end_date)
        
        
        # response = HttpResponse(content_type="text/csv")
        # response["Content-Disposition"] = 'attachment; filename="current-federal.csv"'
        # csv_export.export_data_growth_to_csv(response)
        
        return response

        