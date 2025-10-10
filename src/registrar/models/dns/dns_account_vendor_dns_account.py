from django.db.models import ForeignKey, CASCADE
from ..utility.time_stamped_model import TimeStampedModel


class DnsAccount_VendorDnsAccount(TimeStampedModel):
    dns_account = ForeignKey("registrar.DnsAccount", on_delete=CASCADE, related_name="account_link")
    vendor_dns_account = ForeignKey(
        "registrar.VendorDnsAccount", on_delete=CASCADE, related_name="account_link"
    )  # type: ignore
