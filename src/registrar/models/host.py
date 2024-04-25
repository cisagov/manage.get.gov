from django.db import models

from .utility.time_stamped_model import TimeStampedModel


class Host(TimeStampedModel):
    """
    Hosts are internet-connected computers.

    They may handle email, serve websites, or perform other tasks.

    The registry is the source of truth for this data.

    This model exists to make hosts/nameservers and ip addresses
    available when registry is not available.
    """

    name = models.CharField(
        max_length=253,
        null=False,
        blank=False,
        default=None,  # prevent saving without a value
        unique=False,
        verbose_name="host name",
    )

    domain = models.ForeignKey(
        "registrar.Domain",
        on_delete=models.PROTECT,
        related_name="host",  # access this Host via the Domain as `domain.host`
        help_text="Domain associated with this host",
    )

    def __str__(self):
        return f"{self.domain.name} {self.name}"
