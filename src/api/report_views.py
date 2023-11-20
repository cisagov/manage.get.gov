"""Internal API views"""
from django.apps import apps
from django.views.decorators.http import require_http_methods
from django.http import FileResponse, JsonResponse

import requests


from registrar.utility import csv_export
from login_required import login_not_required

@require_http_methods(["GET"])
@login_not_required
def get_current_full(request):
    # Generate the CSV file
    with open("current-full.csv", "w") as file:
        csv_export.export_data_full_to_csv(file)

    # Serve the CSV file
    response = FileResponse(open('current-full.csv', 'rb'))
    return response

@require_http_methods(["GET"])
@login_not_required
def get_current_federal(request):
    # Generate the CSV file
    with open("current-federal.csv", "w") as file:
        csv_export.export_data_federal_to_csv(file)

    # Serve the CSV file
    response = FileResponse(open('current-federal.csv', 'rb'))
    return response
