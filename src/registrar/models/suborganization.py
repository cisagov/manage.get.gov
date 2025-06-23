from django.db import models

from registrar.models.domain_request import DomainRequest
from .utility.time_stamped_model import TimeStampedModel
from django.db.models.functions import Lower


class Suborganization(TimeStampedModel):
    """
    Suborganization under an organization (portfolio)
    """

    name = models.CharField(
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

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["portfolio", "name"], name="unique_portfolio_name"),
            models.UniqueConstraint(
                fields=["name"], condition=~models.Q(state="deleted", name="unique_name_except_deleted")
            ),
            models.UniqueConstraint(expressions=[Lower("name")], name="unique_lowercase_name"),
        ]

    def __str__(self) -> str:
        return f"{self.name}"
