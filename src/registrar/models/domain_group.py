from django.db import models
from .utility.time_stamped_model import TimeStampedModel


class DomainGroup(TimeStampedModel):

    class Meta:
        unique_together = [("name", "portfolio")]

    """
    Organized group of domains.
    """
    name = models.CharField(
        unique=True,
        help_text="Domain group",
    )

    portfolio = models.ForeignKey("registrar.Portfolio", on_delete=models.PROTECT)

    domains = models.ManyToManyField("registrar.DomainInformation", blank=True)

    def __str__(self) -> str:
        return f"{self.name}"
