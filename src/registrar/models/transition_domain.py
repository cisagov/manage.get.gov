from django.db import models

from .utility.time_stamped_model import TimeStampedModel


class TransitionDomain(TimeStampedModel):
    """Transition Domain model stores information about the
    state of a domain upon transition between registry
    providers"""

    class StatusChoices(models.TextChoices):
        CREATED = "created", "Created"
        HOLD = "hold", "Hold"

    username = models.TextField(
        null=False,
        blank=False,
        verbose_name="Username",
        help_text="Username - this will be an email address",
    )
    domain_name = models.TextField(
        null=True,
        blank=True,
        verbose_name="Domain name",
    )
    status = models.CharField(
        max_length=255,
        null=False,
        blank=True,
        choices=StatusChoices.choices,
        verbose_name="Status",
        help_text="domain status during the transfer",
    )
    ignoreServerHold = models.BooleanField(
        null=False,
        default=False,
        verbose_name="ignore Server Hold",
        help_text="specifies whether to ignore server hold",
    )
    email_sent = models.BooleanField(
        null=False,
        default=False,
        verbose_name="email sent",
        help_text="indicates whether email was sent",
    )

    def __str__(self):
        return self.username
