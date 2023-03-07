from django.contrib.auth.models import AbstractUser

from phonenumber_field.modelfields import PhoneNumberField  # type: ignore


class User(AbstractUser):
    """
    A custom user model that performs identically to the default user model
    but can be customized later.
    """

    phone = PhoneNumberField(
        null=True,
        blank=True,
        help_text="Phone",
        db_index=True,
    )

    def __str__(self):
        # this info is pulled from Login.gov
        if self.first_name or self.last_name:
            return f"{self.first_name or ''} {self.last_name or ''}"
        elif self.email:
            return self.email
        else:
            return self.username
