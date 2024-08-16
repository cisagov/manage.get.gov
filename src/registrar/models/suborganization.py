from django.db import models
from .utility.time_stamped_model import TimeStampedModel


class Suborganization(TimeStampedModel):
    """
    Suborganization under an organization (portfolio)
    """

    name = models.CharField(
        unique=True,
        max_length=1000,
        help_text="Suborganization",
    )

    portfolio = models.ForeignKey(
        "registrar.Portfolio",
        on_delete=models.PROTECT,
        related_name="portfolio_suborganizations",
    )

    def __str__(self) -> str:
        return f"{self.name}"
