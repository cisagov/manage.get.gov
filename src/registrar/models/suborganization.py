from django.db import models
from registrar.models.domain_request import DomainRequest
from .utility.time_stamped_model import TimeStampedModel


class Suborganization(TimeStampedModel):
    """
    Suborganization under an organization (portfolio)
    """

    name = models.CharField(
        unique=True,
        max_length=1000,
        verbose_name="Suborganization",
    )

    portfolio = models.ForeignKey(
        "registrar.Portfolio",
        on_delete=models.PROTECT,
        related_name="portfolio_suborganizations",
    )

    city = models.CharField(
        null=True,
        blank=True,
    )

    state_territory = models.CharField(
        max_length=2,
        choices=DomainRequest.StateTerritoryChoices.choices,
        null=True,
        blank=True,
        verbose_name="state, territory, or military post",
    )

    def __str__(self) -> str:
        return f"{self.name}"
