from django.db import models
from .utility.time_stamped_model import TimeStampedModel
from phonenumber_field.modelfields import PhoneNumberField  # type: ignore


class StatusChoices(models.TextChoices):
    READY = "ready", "Ready"
    ON_HOLD = "on hold", "On hold"
    UNKNOWN = "unknown", "Unknown"


class TransitionDomain(TimeStampedModel):
    """Transition Domain model stores information about the
    state of a domain upon transition between registry
    providers"""

    # This is necessary to expose the enum to external
    # classes that import TransitionDomain
    StatusChoices = StatusChoices

    username = models.CharField(
        null=False,
        blank=False,
        verbose_name="Username",
        help_text="Username - this will be an email address",
    )
    domain_name = models.CharField(
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
    processed = models.BooleanField(
        null=False,
        default=True,
        verbose_name="Processed",
        help_text="Indicates whether this TransitionDomain was already processed",
    )
    organization_type = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Type of organization",
    )
    organization_name = models.CharField(
        null=True,
        blank=True,
        help_text="Organization name",
        db_index=True,
    )
    federal_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Federal government branch",
    )
    federal_agency = models.CharField(
        null=True,
        blank=True,
        help_text="Federal agency",
    )
    epp_creation_date = models.DateField(
        null=True,
        help_text=("Duplication of registry's creation " "date saved for ease of reporting"),
    )
    epp_expiration_date = models.DateField(
        null=True,
        help_text=("Duplication of registry's expiration " "date saved for ease of reporting"),
    )
    first_name = models.CharField(
        null=True,
        blank=True,
        help_text="First name",
        verbose_name="first name / given name",
        db_index=True,
    )
    middle_name = models.CharField(
        null=True,
        blank=True,
        help_text="Middle name (optional)",
    )
    last_name = models.CharField(
        null=True,
        blank=True,
        help_text="Last name",
    )
    title = models.CharField(
        null=True,
        blank=True,
        help_text="Title",
    )
    email = models.EmailField(
        null=True,
        blank=True,
        help_text="Email",
    )
    phone = PhoneNumberField(
        null=True,
        blank=True,
        help_text="Phone",
    )
    address_line = models.CharField(
        null=True,
        blank=True,
        help_text="Street address",
    )
    city = models.CharField(
        null=True,
        blank=True,
        help_text="City",
    )
    state_territory = models.CharField(
        max_length=2,
        null=True,
        blank=True,
        help_text="State, territory, or military post",
    )
    zipcode = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text="Zip code",
        db_index=True,
    )

    def __str__(self):
        return f"{self.username}, {self.domain_name}"

    def display_transition_domain(self):
        """Displays all information about a TransitionDomain in string format"""
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
            f"first_name: {self.first_name}, \n"
            f"middle_name: {self.middle_name}, \n"
            f"last_name: {self.last_name}, \n"
            f"email: {self.email}, \n"
            f"phone: {self.phone}, \n"
            f"address_line: {self.address_line}, \n"
            f"city: {self.city}, \n"
            f"state_territory: {self.state_territory}, \n"
            f"zipcode: {self.zipcode}, \n"
        )
