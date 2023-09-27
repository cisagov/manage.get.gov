from django.db import models

from .utility.time_stamped_model import TimeStampedModel


class StatusChoices(models.TextChoices):
    READY = "ready", "Ready"
    HOLD = "hold", "Hold"


class TransitionDomain(TimeStampedModel):
    """Transition Domain model stores information about the
    state of a domain upon transition between registry
    providers"""

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
        default=StatusChoices.READY,
        choices=StatusChoices.choices,
        verbose_name="Status",
        help_text="domain status during the transfer",
    )
    email_sent = models.BooleanField(
        null=False,
        default=False,
        verbose_name="email sent",
        help_text="indicates whether email was sent",
    )

    def __str__(self):
        return (
            f"username: {self.username} "
            f"domainName: {self.domain_name} "
            f"status: {self.status} "
            f"email sent: {self.email_sent} "
        )
