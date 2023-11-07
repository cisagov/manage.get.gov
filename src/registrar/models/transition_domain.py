from django.db import models
from .utility.time_stamped_model import TimeStampedModel


class StatusChoices(models.TextChoices):
    READY = "ready", "Ready"
    ON_HOLD = "on hold", "On Hold"


class TransitionDomain(TimeStampedModel):
    """Transition Domain model stores information about the
    state of a domain upon transition between registry
    providers"""

    # This is necessary to expose the enum to external
    # classes that import TransitionDomain
    StatusChoices = StatusChoices

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
    organization_type = models.TextField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Type of organization",
    )
    organization_name = models.TextField(
        null=True,
        blank=True,
        help_text="Organization name",
        db_index=True,
    )
    federal_type = models.TextField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Federal government branch",
    )
    federal_agency = models.TextField(
        null=True,
        blank=True,
        help_text="Federal agency",
    )
    epp_creation_date = models.DateField(
        null=True,
        help_text=(
            "Duplication of registry's creation " "date saved for ease of reporting"
        ),
    )
    epp_expiration_date = models.DateField(
        null=True,
        help_text=(
            "Duplication of registry's expiration " "date saved for ease of reporting"
        ),
    )

    def __str__(self):

        return f"""
        username="{self.username}",
        domain_name="{self.domain_name}",
        status="{self.status}",
        email_sent={self.email_sent},
        organization_type="{self.organization_type}",
        organization_name="{self.organization_name}",
        federal_type="{self.federal_type}",
        federal_agency="{self.federal_agency}",
        epp_creation_date={self.epp_creation_date},
        epp_expiration_date={self.epp_expiration_date}
        """
        """
        return (
            f"\n-----TRANSITION DOMAIN------\n"
            f"domainName: {self.domain_name}, \n"
            f"username: {self.username}, \n"
            f"status: {self.status}, \n"
            f"email sent: {self.email_sent}, \n"
            f"organization type: {self.organization_type}, \n"
            f"organization_name: {self.organization_name}, \n"
            f"federal_type: {self.federal_type}, \n"
            f"federal_agency: {self.federal_agency}, \n"
            f"epp_creation_date: {self.epp_creation_date}, \n"
            f"epp_expiration_date: {self.epp_expiration_date}, \n"
        )"""
