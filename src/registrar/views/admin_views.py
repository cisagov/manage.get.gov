"""Admin-related views."""

from django.http import HttpResponse
from django.views import View

from registrar.utility import csv_export

import logging

logger = logging.getLogger(__name__)


class ExportData(View):
    def get(self, request, *args, **kwargs):
        # Get start_date and end_date from the request's GET parameters
        # #999: not needed if we switch to django forms
        start_date = request.GET.get("start_date", "")
        end_date = request.GET.get("end_date", "")

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="domain-growth-report-{start_date}-to-{end_date}.csv"'
        # For #999: set export_data_growth_to_csv to return the resulting queryset, which we can then use
        # in context to display this data in the template.
        csv_export.export_data_growth_to_csv(response, start_date, end_date)

        return response
