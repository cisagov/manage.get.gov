from django.db import models
from .utility.time_stamped_model import TimeStampedModel
from registrar.models.portfolio import Portfolio


class Suborganization(TimeStampedModel):
    """
    Suborganization under an organization (portfolio)
    """
    name = models.CharField(
        null=True,
        blank=True,
        unique=True,
        help_text="Suborganization",
    )

    portfolio = models.ForeignKey(
        "registrar.Portfolio",
        on_delete=models.PROTECT,
    )

    def __str__(self) -> str:
        return f"{self.name}"
