from django.db import models

from registrar.models.domain_request import DomainRequest
from .utility.time_stamped_model import TimeStampedModel
from django.core.exceptions import ValidationError


class Suborganization(TimeStampedModel):
    """
    Suborganization under an organization (portfolio)
    """

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["name", "portfolio"], name="unique_name_portfolio")]

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

    def __str__(self) -> str:
        return f"{self.name}"

    def clean(self):
        if (
            Suborganization.objects.exclude(pk=self.pk)
            .filter(
                portfolio=self.portfolio,
                name__iexact=self.name,
            )
            .exists()
        ):
            raise ValidationError({"name": "Suborganization name already exists in Portfolio"})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
