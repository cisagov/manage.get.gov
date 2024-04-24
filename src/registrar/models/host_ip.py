from django.db import models
from django.core.validators import validate_ipv46_address

from .utility.time_stamped_model import TimeStampedModel


class HostIP(TimeStampedModel):
    """
    Hosts may have one or more IP addresses.

    The registry is the source of truth for this data.

    This model exists to make hosts/nameservers and ip addresses
    available when registry is not available.
    """

    address = models.CharField(
        max_length=46,
        null=False,
        blank=False,
        default=None,  # prevent saving without a value
        validators=[validate_ipv46_address],
        verbose_name="IP address",
    )

    host = models.ForeignKey(
        "registrar.Host",
        on_delete=models.PROTECT,
        related_name="ip",  # access this HostIP via the Host as `host.ip`
        help_text="IP associated with this host",
    )
