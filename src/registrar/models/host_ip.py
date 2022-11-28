from django.db import models
from django.core.validators import validate_ipv46_address

from .utility.time_stamped_model import TimeStampedModel
from .host import Host


class HostIP(TimeStampedModel):
    """
    Hosts may have one or more IP addresses.

    The registry is the source of truth for this data.

    This model exists ONLY to allow a new registrant to draft DNS entries
    before their application is approved.
    """

    address = models.CharField(
        max_length=46,
        null=False,
        blank=False,
        default=None,  # prevent saving without a value
        validators=[validate_ipv46_address],
        help_text="IP address",
    )

    host = models.ForeignKey(
        Host,
        on_delete=models.PROTECT,
        related_name="ip",  # access this HostIP via the Host as `host.ip`
        help_text="Host to which this IP address belongs",
    )
