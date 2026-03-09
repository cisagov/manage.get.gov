from registrar.forms.domain import ARecordForm, TXTRecordForm
from registrar.utility.enums import DNSRecordTypes
from registrar.decorators import IS_STAFF, grant_access
from django.template.response import TemplateResponse
from django.http import HttpResponse

FORM_MAP = {DNSRecordTypes.A: ARecordForm, DNSRecordTypes.AAAA: ARecordForm, DNSRecordTypes.TXT: TXTRecordForm}


def get_partial_string_path(type):
    if type in [DNSRecordTypes.A, DNSRecordTypes.AAAA]:
        return "dns_record_forms/base_dns_form.html"
    else:
        record_type_lower = type.lower()
        return f"dns_record_forms/{record_type_lower}_dns_form.html"


@grant_access(IS_STAFF)
def get_dns_form_partial(request):
    record_type = request.GET.get("type")
    if not record_type:
        return HttpResponse("")
    form = FORM_MAP.get(record_type)
    partial_url = get_partial_string_path(record_type)
    template = f"../templates/{partial_url}"
    return TemplateResponse(request, template, {"form": form})
