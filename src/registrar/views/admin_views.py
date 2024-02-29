"""Admin-related views."""

from django.http import HttpResponse
from django.views import View

from registrar.utility import csv_export

import logging

logger = logging.getLogger(__name__)
    
class ExportDataType(View):
    def get(self, request, *args, **kwargs):
        # match the CSV example with all the fields
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="domains-by-type.csv"'
        csv_export.export_data_type_to_csv(response)
        return response
    
class ExportDataFull(View):
    def get(self, request, *args, **kwargs):
        # Smaller export based on 1
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="current-full.csv"'
        csv_export.export_data_full_to_csv(response)
        return response
    
class ExportDataFederal(View):
    def get(self, request, *args, **kwargs):
        # Federal only
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="current-federal.csv"'
        csv_export.export_data_federal_to_csv(response)
        return response

class ExportDataDomainGrowth(View):
    def get(self, request, *args, **kwargs):
        # Get start_date and end_date from the request's GET parameters
        # #999: not needed if we switch to django forms
        start_date = request.GET.get("start_date", "")
        end_date = request.GET.get("end_date", "")

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="domain-growth-report-{start_date}-to-{end_date}.csv"'
        # For #999: set export_data_domain_growth_to_csv to return the resulting queryset, which we can then use
        # in context to display this data in the template.
        csv_export.export_data_domain_growth_to_csv(response, start_date, end_date)

        return response
    
class ExportDataManagedVsUnmanaged(View):
    def get(self, request, *args, **kwargs):
        # Get start_date and end_date from the request's GET parameters
        # #999: not needed if we switch to django forms
        start_date = request.GET.get("start_date", "")
        end_date = request.GET.get("end_date", "")
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="managed-vs-unamanaged-domains-{start_date}-to-{end_date}.csv"'
        csv_export.export_data_managed_vs_unamanaged_domains(response, start_date, end_date)

        return response
    
class ExportDataRequests(View):
    def get(self, request, *args, **kwargs):
        # Get start_date and end_date from the request's GET parameters
        # #999: not needed if we switch to django forms
        start_date = request.GET.get("start_date", "")
        end_date = request.GET.get("end_date", "")

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="requests-{start_date}-to-{end_date}.csv"'
        # For #999: set export_data_domain_growth_to_csv to return the resulting queryset, which we can then use
        # in context to display this data in the template.
        csv_export.export_data_requests_to_csv(response, start_date, end_date)

        return response