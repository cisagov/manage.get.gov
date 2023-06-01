from django.db import models

from phonenumber_field.modelfields import PhoneNumberField  # type: ignore

from .utility.time_stamped_model import TimeStampedModel


class Contact(TimeStampedModel):

    """Contact information follows a similar pattern for each contact."""

    user = models.OneToOneField(
        "registrar.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    first_name = models.TextField(
        null=True,
        blank=True,
        help_text="First name",
        verbose_name="first name / given name",
        db_index=True,
    )
    middle_name = models.TextField(
        null=True,
        blank=True,
        help_text="Middle name",
    )
    last_name = models.TextField(
        null=True,
        blank=True,
        help_text="Last name",
        verbose_name="last name / family name",
        db_index=True,
    )
    title = models.TextField(
        null=True,
        blank=True,
        help_text="Title",
        verbose_name="title or role in your organization",
    )
    email = models.EmailField(
        null=True,
        blank=True,
        help_text="Email",
        db_index=True,
    )
    phone = PhoneNumberField(
        null=True,
        blank=True,
        help_text="Phone",
        db_index=True,
    )

    def get_formatted_name(self):
        """Returns the contact's name in Western order."""
        names = [n for n in [self.first_name, self.middle_name, self.last_name] if n]
        return " ".join(names) if names else "Unknown"

    def __str__(self):
        if self.first_name or self.last_name:
            return self.get_formatted_name()
        elif self.email:
            return self.email
        elif self.pk:
            return str(self.pk)
        else:
            return ""
