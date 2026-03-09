from registrar.forms.domain import ARecordForm, TXTRecordForm
from registrar.utility.enums import DNSRecordTypes
from registrar.decorators import (IS_STAFF, grant_access)
from django.template.response import TemplateResponse

FORM_MAP = {
        DNSRecordTypes.A: ARecordForm,
        DNSRecordTypes.AAAA: ARecordForm,
        DNSRecordTypes.TXT: TXTRecordForm
}

def get_partial_string_path(type):
    if type in [DNSRecordTypes.A, DNSRecordTypes.AAAA]:
        return "dns_record_partials/_a_form_partial.html"
    else:
        record_type_lower = type.lower()
        return f"dns_record_partials/_{record_type_lower}_form_partial.html"



@grant_access(IS_STAFF)
def get_dns_form_partial(request):
    record_type = request.GET.get("type")
    form = FORM_MAP.get(record_type)
    partial_url = get_partial_string_path(record_type)
    template = f"../templates/{partial_url}"
    return TemplateResponse(request, template, {"form" : form})