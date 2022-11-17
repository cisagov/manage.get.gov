from django.db import models

from .utility.time_stamped_model import TimeStampedModel
from .domain import Domain


class Host(TimeStampedModel):
    """
    Hosts are internet-connected computers.

    They may handle email, serve websites, or perform other tasks.

    The registry is the source of truth for this data.

    This model exists ONLY to allow a new registrant to draft DNS entries
    before their application is approved.
    """

    name = models.CharField(
        max_length=253,
        null=False,
        blank=False,
        default=None,  # prevent saving without a value
        unique=True,
        help_text="Fully qualified domain name",
    )

    domain = models.ForeignKey(
        Domain,
        on_delete=models.PROTECT,
        help_text="Domain to which this host belongs",
    )
